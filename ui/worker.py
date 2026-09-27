"""The pipeline worker: model, source and stream session, off the UI thread.

`PipelineWorker` is a `QObject` meant to be moved onto its own `QThread`. The
UI thread never touches the model, the source or the stream session: it sends
commands through queued signals (the slots below) and receives each frame as a
`FramePayload`. The frame order itself is `core.pipeline`'s -- this module only
decides *when* a frame runs.

A stream does not block the worker's thread in a loop. Each frame is one tick,
queued behind whatever command arrived meanwhile, so stop, pause, a click or a
new threshold is handled between two frames with no locking at all. A tick
from a stream that has since been stopped carries an old generation number
and does nothing.

Opening a source checks in the order `detect.main` does: the rules (streams
only), then the weights, then the source -- a broken `rules.yaml` or missing
weights never switch a camera on. Every way out of a stream closes the
session's files and the source, and says the same summary line `detect.py`
prints.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np
from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal, Slot

import detect
from core import events, output, pipeline
from core.config import Config
from core.detector import require_weights
from core.rules import Event, RuleSet
from core.source import is_stream_spec
from core.types import Detection, Frame

log = logging.getLogger("vision.ui.worker")


@dataclass(frozen=True)
class FramePayload:
    """One frame for the UI thread: data only, sharing no memory with the worker.

    `total` is the number of frames the source has, 0 when unknown (a camera).
    `fps` is 0 for a photo.
    """

    canvas: np.ndarray
    drawn: list[Detection]
    near_miss_count: int
    target_track_id: int | None
    index: int
    total: int
    fps: float
    source: str
    is_stream: bool


class PipelineWorker(QObject):
    """Owns the model, the open source and the stream session; runs every frame.

    `detector_factory(cfg)` builds a detector (`core.detector.Detector` in the
    app); `source_factory(spec, cfg)` opens a source (`core.source.Source`).

    Signals: `model_ready(names)`, `model_failed(sentence)`,
    `frame_ready(FramePayload)` for photos and stream frames, `event(line)` --
    the line `output.print_event` prints --, `failed(sentence)` for anything
    the user has to be told, `finished(summary)` when a stream is over (the
    line `output.print_stream_summary` prints), and `applied(Config)` with the
    config the session actually runs after `apply`.

    The UI calls `frame_shown()` once for every `frame_ready` it has taken.
    Until then the worker keeps processing and writing every frame but sends
    none, holding only the newest: at most one unshown frame is ever in flight
    (plus a stream's last frame at its natural end).
    """

    model_ready = Signal(object)  # dict[int, str]; a Qt dict would drop the int keys
    model_failed = Signal(str)
    frame_ready = Signal(object)
    event = Signal(str)
    failed = Signal(str)
    finished = Signal(str)
    applied = Signal(object)

    def __init__(
        self,
        cfg: Config,
        detector_factory: Callable[[Config], Any],
        source_factory: Callable[[str, Config], Any],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._detector_factory = detector_factory
        self._source_factory = source_factory
        self._detector: Any = None
        self._model_error = ""
        self._source: Any = None
        self._generation = 0  # bumped on every open and stop; old ticks see a stale value
        # A photo or a folder: index -> (frame, every detection from conf_debug up).
        self._stills: dict[int, tuple[Frame, list[Detection]]] = {}
        self._still_frames: Iterator[Frame] | None = None
        self._still_next = 0  # index the still iterator yields next
        self._still_index: int | None = None
        self._still_result: pipeline.StillResult | None = None
        # A stream.
        self._session: pipeline.StreamSession | None = None
        self._rule_set: RuleSet | None = None
        self._frames: Iterator[Frame] | None = None
        self._paused = False
        self._last_frame: Frame | None = None  # the stream frame on screen
        # Display pacing: payloads sent but not yet acknowledged by `frame_shown`,
        # and the newest frame waiting for that acknowledgement.
        self._unshown = 0
        self._held: FramePayload | None = None

    # --- the model -----------------------------------------------------------

    @Slot()
    def load_model(self) -> None:
        """Build the detector from the session config; `model_ready` or `model_failed`."""
        detector = self._build(self._cfg)
        if detector is not None:
            self._detector = detector
            self.model_ready.emit(detector.names)

    def _build(self, cfg: Config) -> Any:
        """A new detector for `cfg`, or None after saying why it could not be built."""
        try:
            detector = self._detector_factory(cfg)
        # Anything: besides the one-sentence missing-weights errors, a damaged
        # weights file surfaces from deep inside torch or OpenVINO.
        except Exception as err:  # noqa: BLE001 -- the old model keeps running
            log.warning("model not loaded: %s", err)
            self._model_error = str(err)
            self.model_failed.emit(str(err))
            return None
        self._model_error = ""
        return detector

    # --- opening and closing ----------------------------------------------------

    @Slot(str)
    def open_source(self, spec: str) -> None:
        """Stop whatever runs, then open `spec`: a photo, a folder, a video or a camera."""
        self.stop()
        rule_set = None
        try:
            if is_stream_spec(spec):
                # Before the source: a broken rules.yaml must not switch a camera on.
                rule_set = detect.prepare_rules(self._cfg)
            require_weights(self._cfg)
            if self._detector is None:
                raise RuntimeError(self._model_error or "the model is not loaded")
            source = self._source_factory(spec, self._cfg)
        except (FileNotFoundError, ValueError, OSError, RuntimeError) as err:
            if rule_set is not None and rule_set.calls():
                events.clear()
            self.failed.emit(str(err))
            return

        if source.is_stream and rule_set is None:
            # A stream the spec did not announce: its rules are still checked first.
            try:
                rule_set = detect.prepare_rules(self._cfg)
            except (FileNotFoundError, ValueError) as err:
                source.close()
                self.failed.emit(str(err))
                return

        self._source = source
        self._rule_set = rule_set
        self._generation += 1
        try:
            if source.is_stream:
                self._start_stream(source)
            else:
                self._start_stills()
        # Anything: the source is open, and whatever broke between here and the
        # first frame (the tracker's import, the session) must not keep it so.
        except Exception as err:  # noqa: BLE001 -- the app stays alive, the source closes
            log.exception("source could not start")
            self._fail(str(err))

    @Slot()
    def stop(self) -> None:
        """End the current source: close a stream's files and the source, say the summary."""
        self._generation += 1
        source, self._source = self._source, None
        session, self._session = self._session, None
        frames, self._frames = self._frames, None
        rule_set, self._rule_set = self._rule_set, None
        self._paused = False
        self._last_frame = None
        self._held = None  # an explicit stop drops it: the UI has moved on
        self._reset_stills()
        try:
            if frames is not None:
                close = getattr(frames, "close", None)
                if close is not None:
                    close()
            if session is not None:
                paths = session.close()
                self.finished.emit(output.format_summary(session.frames, session.fired, paths))
        finally:
            if source is not None:
                source.close()
            if rule_set is not None and rule_set.calls():
                events.clear()  # the registry is module state: the next stream loads anew

    @Slot()
    def shutdown(self) -> None:
        """Stop, then end the worker's thread -- the last command before the window closes.

        Queued behind the frame in progress, so the camera is released before
        the owner's `QThread.wait()` returns.
        """
        self.stop()
        thread = self.thread()
        if thread is not None and thread != _main_thread():
            thread.quit()

    # --- photos and folders ---------------------------------------------------------

    def _start_stills(self) -> None:
        self._still_frames = iter(self._source)
        self._still_next = 0
        self.show_index(0)

    def _reset_stills(self) -> None:
        self._stills = {}
        self._still_frames = None
        self._still_next = 0
        self._still_index = None
        self._still_result = None

    @Slot(int)
    def show_index(self, index: int) -> None:
        """Show photo `index` of the open photo or folder; the model runs once per photo."""
        if self._source is None or self._source.is_stream:
            return
        if not 0 <= index < len(self._source):
            return
        cached = self._stills.get(index)
        try:
            if cached is None:
                still = self._read_still(index)
                result = pipeline.process_still(still, self._detector, self._cfg, self._color)
                self._stills[index] = (still, result.detections)
                self._still_index, self._still_result = index, result
                self._emit_still(still, result)
                pipeline.save_still(still.source, result, self._cfg)
                for detection in result.drawn:
                    events.emit(detection)
            else:
                still, detections = cached
                result = pipeline.resplit_still(still, detections, self._cfg, self._color)
                self._still_index, self._still_result = index, result
                self._emit_still(still, result)
        except (FileNotFoundError, ValueError, OSError) as err:
            self.failed.emit(str(err))

    def _read_still(self, index: int) -> Frame:
        """Frame `index` of the photo source, reading forward from where it stands."""
        if self._still_frames is None or index < self._still_next:
            self._still_frames = iter(self._source)
            self._still_next = 0
        for still in self._still_frames:
            self._still_next += 1
            if self._still_next - 1 == index:
                return still
        raise ValueError(f"no photo number {index} in the source")

    def _emit_still(self, still: Frame, result: pipeline.StillResult) -> None:
        self._post(FramePayload(
            canvas=result.canvas.copy(), drawn=_copies(result.drawn),
            near_miss_count=len(result.near_miss), target_track_id=None,
            index=still.index, total=len(self._source), fps=0.0,
            source=still.source, is_stream=False,
        ))

    def _redraw_still(self) -> None:
        """Split and draw the current photo again under the session config, no model."""
        if self._still_index is None:
            return
        still, detections = self._stills[self._still_index]
        self._still_result = pipeline.resplit_still(still, detections, self._cfg, self._color)
        self._emit_still(still, self._still_result)

    @Slot()
    def commit_still(self) -> None:
        """Rewrite the current photo's files to match what is on screen."""
        if self._still_index is None or self._still_result is None:
            return
        still, _ = self._stills[self._still_index]
        try:
            pipeline.save_still(still.source, self._still_result, self._cfg)
        except OSError as err:
            self.failed.emit(str(err))

    # --- streams -----------------------------------------------------------------------

    def _start_stream(self, source: Any) -> None:
        self._session = pipeline.StreamSession(
            self._detector, self._cfg, self._rule_set, source.fps, source.frame_size,
            # Only a video file gets an .mp4 back; a camera's frames go to the JSONL.
            is_video=not source.is_camera,
            on_log=self._log_event,
            want_color=self._color,
        )
        self._frames = iter(source)
        self._schedule()

    def _log_event(self, event: Event) -> None:
        self.event.emit(output.format_event(event))

    def _schedule(self) -> None:
        generation = self._generation
        QTimer.singleShot(0, self, lambda: self._tick(generation))

    def _tick(self, generation: int) -> None:
        """Run one stream frame, then queue the next one behind any waiting command."""
        if generation != self._generation or self._session is None or self._paused:
            return
        try:
            frame = next(self._frames)
        except StopIteration:
            self._flush()  # a finished video leaves its last frame on screen
            self.stop()
            return
        except OSError as err:  # the camera stopped delivering frames
            self._fail(str(err))
            return
        try:
            result = self._session.step(frame)
        except pipeline.StreamWriteError as err:
            # Only one of the stream's own files; an OSError from the model or
            # a handler is not a write error and is reported below as it is.
            self._fail(str(err))
            return
        except Exception as err:  # noqa: BLE001 -- the app stays alive, the stream ends
            log.exception("stream frame failed")
            self._fail(str(err))
            return

        self._last_frame = frame
        self._emit_stream(frame, result)
        self._schedule()

    def _emit_stream(self, frame: Frame, result: pipeline.StreamResult) -> None:
        target = result.target.detection
        self._post(FramePayload(
            canvas=result.canvas.copy(), drawn=_copies(result.drawn),
            near_miss_count=len(result.near_miss),
            target_track_id=None if target is None else target.track_id,
            index=frame.index, total=len(self._source), fps=self._session.fps,
            source=frame.source, is_stream=True,
        ))

    def _redraw_paused(self) -> None:
        """On a paused video, show the held frame again at once: new target or threshold."""
        if self._paused and self._session is not None and self._last_frame is not None:
            self._emit_stream(self._last_frame, self._session.redraw())

    def _fail(self, sentence: str) -> None:
        self._flush()
        self.failed.emit(sentence)
        self.stop()

    @Slot()
    def frame_shown(self) -> None:
        """The UI is done with one payload; the newest held one, if any, goes out now."""
        self._unshown = max(0, self._unshown - 1)
        if self._unshown == 0 and self._held is not None:
            held, self._held = self._held, None
            self._post(held)

    def _post(self, payload: FramePayload) -> None:
        """Send a frame to the UI, or hold it while the UI has not taken the last one.

        Every frame is processed and written regardless; only the display is
        coalesced, so an unpaced video never floods the UI thread's queue.
        """
        if self._unshown:
            self._held = payload  # a newer one replaces the older unsent one
            return
        self._unshown += 1
        self.frame_ready.emit(payload)

    def _flush(self) -> None:
        """At a stream's natural end: its last frame goes out even while one is unshown."""
        held, self._held = self._held, None
        if held is not None:
            self._unshown += 1
            self.frame_ready.emit(held)

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        """Hold or resume a video file; a camera cannot be paused."""
        if self._session is None or self._source.is_camera or paused == self._paused:
            return
        self._paused = paused
        # A tick queued before the pause must not run alongside the resumed chain.
        self._generation += 1
        if not paused:
            self._schedule()

    @Slot(float, float)
    def click(self, x: float, y: float) -> None:
        """Lock onto the tracked box under `(x, y)` in frame pixels, or release."""
        if self._session is not None:
            self._session.click((x, y))
            self._redraw_paused()

    # --- threshold and settings ------------------------------------------------------

    @Slot(float)
    def set_conf(self, conf: float) -> None:
        """A new drawing threshold: a photo is redrawn now, a stream from the next frame."""
        self._cfg = dataclasses.replace(
            self._cfg, model=dataclasses.replace(self._cfg.model, conf=conf)
        )
        self._retune()

    @Slot(object)
    def apply(self, cfg: Config) -> None:
        """Run the session on `cfg`; the threshold stays `set_conf`'s.

        A new model or `imgsz` reloads the detector (a stream keeps its tracks);
        new classes go to the loaded model; anything else only redraws. A model
        that will not load leaves the old one and its settings running, and a
        class the model does not know leaves the old classes.
        """
        old = self._cfg
        cfg = dataclasses.replace(
            cfg, model=dataclasses.replace(
                cfg.model, conf=old.model.conf, conf_debug=old.model.conf_debug
            )
        )
        rerun = False
        if (cfg.model.weights, cfg.model.imgsz) != (old.model.weights, old.model.imgsz):
            detector = self._build(cfg)
            if detector is None:
                cfg = dataclasses.replace(cfg, model=old.model, classes=old.classes)
            else:
                self._detector = detector
                if self._session is not None:
                    self._session.set_detector(detector)
                rerun = True
                self.model_ready.emit(detector.names)
        elif cfg.classes != old.classes and self._detector is not None:
            try:
                self._detector.set_classes(list(cfg.classes))
                rerun = True
            except ValueError as err:
                self.failed.emit(str(err))
                cfg = dataclasses.replace(cfg, classes=old.classes)

        self._cfg = cfg
        self.applied.emit(cfg)
        if rerun and self._session is None and self._still_index is not None:
            # The cached detections came from the old model or classes.
            index = self._still_index
            self._stills = {}
            self.show_index(index)
            return
        self._retune()

    def _retune(self) -> None:
        if self._session is not None:
            self._session.retune(self._cfg, self._color)
            self._redraw_paused()
        else:
            self._redraw_still()

    @property
    def _color(self) -> bool:
        return self._cfg.display.color


def _copies(detections: list[Detection]) -> list[Detection]:
    """New `Detection` objects: the UI thread gets none the worker still holds."""
    return [dataclasses.replace(detection) for detection in detections]


def _main_thread() -> QThread | None:
    app = QCoreApplication.instance()
    return None if app is None else app.thread()
