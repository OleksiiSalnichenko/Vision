"""The order of one frame, shared by every way the project is launched.

A photo: detect -> split -> colour -> draw, then save. A stream frame: detect
-> track -> split -> colour -> target -> status line -> draw -> rules ->
actions -> record. `detect.py` and the desktop app both run this module, so
there is one frame order and one place where it can change.

This is the only caller of `core.detector.is_debug`. `core.draw`,
`core.output`, `core.target` and `core.rules` are handed ready-made lists and
never learn a threshold -- if the split moved into them, a near-miss would
start being drawn and printed and nothing would say so.

Nothing here prints, and nothing here knows how it was launched. A rule's
`log` action goes to the `on_log` callback the caller hands in; `save_frame`
and `call` are carried out here, the same for every caller. `core.output` and
`core.events` are always reached through the module attribute, so a caller or
a test that replaces one of their functions replaces it here too.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import logging
import time
from collections import deque
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core import aim, draw, events, output
from core.config import Config
from core.detector import is_debug
from core.rules import CALL, Event, RuleEngine, RuleSet, load_rules
from core.target import Targeting, TargetState
from core.tracker import Tracker
from core.types import Detection, Frame

log = logging.getLogger("vision.pipeline")

# Frames the on-screen FPS is averaged over: long enough not to flicker,
# short enough to follow a real slowdown within a couple of seconds.
_FPS_WINDOW = 30


# --- rules and handlers ------------------------------------------------------


def prepare_rules(rules_path: Path, handlers_path: Path) -> RuleSet:
    """Load the rules file and, when a rule calls a function, the handlers file.

    Raises `FileNotFoundError` or `ValueError` with one sentence; on a failure
    the event bus is left empty. On success the handlers stay registered, and
    the caller clears the bus once the stream is over.
    """
    rule_set = load_rules(rules_path)
    if rule_set.calls():
        try:
            _load_handlers(rule_set, Path(handlers_path))
        except BaseException:
            events.clear()
            raise
    return rule_set


def _load_handlers(rule_set: RuleSet, handlers_path: Path) -> None:
    """Run the handlers file so its `@on_detect` functions register, then check names.

    Loaded from its path rather than imported, so a second stream in the same
    process registers the functions again after `events.clear()`. Raises
    `FileNotFoundError` when the file is missing and `ValueError` naming the
    first function a rule calls that nothing registered.
    """
    if not handlers_path.is_file():
        raise FileNotFoundError(f"handlers file not found: {handlers_path}")
    spec = importlib.util.spec_from_file_location("handlers", handlers_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    registered = events.names()
    for name in sorted(rule_set.calls()):
        if name not in registered:
            raise ValueError(f"unknown handler in rules.yaml: {name}")
    _warn_unreachable(rule_set)


def _warn_unreachable(rule_set: RuleSet) -> None:
    """Warn once per rule whose class no handler it calls will ever accept.

    `events.call` keeps the handler's class filter, so a rule on `person`
    calling a handler registered for `cell phone` would fire and do nothing.
    """
    for rule in rule_set.rules:
        if rule.cls is None:
            continue
        for action in rule.actions:
            if not (isinstance(action, tuple) and action[0] == CALL):
                continue
            classes = events.subscriptions(action[1])
            if None not in classes and rule.cls not in classes:
                log.warning(
                    "rule %s is on %s, but %s only listens to %s; it will never run",
                    rule.name, rule.cls, action[1], ", ".join(sorted(classes)),
                )


# --- photos ------------------------------------------------------------------


@dataclass(frozen=True)
class StillResult:
    """One photo after the pipeline.

    `drawn` is what the user sees and what the console lists; `near_miss`
    exists only in the JSON; `detections` is everything the model returned
    from `conf_debug` upwards, kept so `resplit_still` can split it again under
    another threshold without running the model.
    """

    canvas: np.ndarray
    drawn: list[Detection]
    near_miss: list[Detection]
    detections: list[Detection]


def process_still(
    frame: Frame, detector: Callable[[Frame], list[Detection]], cfg: Config, want_color: bool
) -> StillResult:
    """Run the model on one photo, split, colour and draw it. Writes nothing.

    The caller hands each drawn detection to `events.emit`, after it has said
    what it wants to say about the photo.
    """
    return resplit_still(frame, detector(frame), cfg, want_color)


def resplit_still(
    frame: Frame, detections: Sequence[Detection], cfg: Config, want_color: bool
) -> StillResult:
    """Split `detections` under `cfg`'s threshold and draw them again, without the model.

    `detections` itself is left untouched: a colour is filled into copies, so
    a cached photo can be redrawn with colour switched off again.
    """
    everything = list(detections)
    drawn = [item for item in everything if not is_debug(item, cfg)]
    near_miss = [item for item in everything if is_debug(item, cfg)]
    if want_color:
        drawn = _add_colors(frame, drawn)
    canvas = draw.annotate(frame.image, drawn, cfg)
    return StillResult(canvas=canvas, drawn=drawn, near_miss=near_miss, detections=everything)


def save_still(
    source: str,
    result: StillResult,
    cfg: Config,
    on_written: Callable[[Path], None] | None = None,
) -> list[Path]:
    """Write the photo's `_annotated.jpg`, then its `.json`; return what was written.

    A file the config turned off is simply not in the list. `on_written(path)`
    is called for each file right after it is written and before the next one
    is attempted, so a caller that names the files says exactly what reached
    the disk when a later write fails.
    """
    writes = (
        lambda: output.write_image(source, result.canvas, cfg),
        lambda: output.write_json(source, result.drawn, cfg, debug_detections=result.near_miss),
    )
    written: list[Path] = []
    for write in writes:
        path = write()
        if path is None:
            continue
        written.append(path)
        if on_written is not None:
            on_written(path)
    return written


def _add_colors(frame: Frame, detections: list[Detection]) -> list[Detection]:
    """Return copies of `detections` with `color` filled in.

    Imported here and nowhere else: with colour off the scikit-learn import is
    never paid for. Only the drawn boxes are sampled -- a colour is a thing the
    user looks at, and a near-miss is never looked at.
    """
    from core.attributes import dominant_color  # noqa: PLC0415 -- behind the switch

    coloured: list[Detection] = []
    for detection in detections:
        try:
            detection = dataclasses.replace(
                detection, color=dominant_color(frame.image, detection.bbox)
            )
        except ValueError as err:  # a box too small or too far off the frame
            log.warning("no colour for %s: %s", detection.cls_name, err)
        coloured.append(detection)
    return coloured


# --- streams -----------------------------------------------------------------


class StreamWriteError(OSError):
    """A stream's own file -- an event frame, the JSONL, the .mp4 -- could not be written.

    Raised by `StreamSession.step` in place of the `OSError` from the write,
    with the same message, so a caller can tell an unwritable file from an
    `OSError` anywhere else in the frame (the model, a handler), which
    `step` lets through untouched.
    """


@dataclass(frozen=True)
class StreamResult:
    """One stream frame after the pipeline, its actions already carried out."""

    canvas: np.ndarray
    drawn: list[Detection]
    near_miss: list[Detection]
    target: TargetState
    events: tuple[Event, ...]
    status: str


class StreamSession:
    """One video or camera stream: tracker, target, rules and files, frame by frame.

    A new session per stream: rule cooldowns are keyed by track id, and a new
    tracker numbers its tracks from 1 again. Files open on the first `step`
    and are closed by `close()` or on the way out of a `with` block.
    """

    def __init__(
        self,
        detector: Callable[[Frame], list[Detection]],
        cfg: Config,
        rule_set: RuleSet,
        fps: float,
        frame_size: tuple[int, int] | None,
        is_video: bool,
        on_log: Callable[[Event], None],
        want_color: bool,
    ) -> None:
        self._detector = detector
        self._cfg = cfg
        self._fps_in = fps
        self._frame_size = frame_size
        self._is_video = is_video  # only a video file gets an .mp4 back
        self._on_log = on_log
        self._want_color = want_color
        self._tracker = Tracker(cfg)
        self._targeting = Targeting(cfg)
        self._engine = RuleEngine(rule_set)
        self._writer: output.StreamWriter | None = None
        self._ticks: deque[float] = deque(maxlen=_FPS_WINDOW)
        self._on_screen: list[Detection] = []  # the drawn detections of the last frame
        # The last frame and everything the tracker returned for it, for `redraw`.
        self._last: tuple[Frame, list[Detection]] | None = None
        self._paths: list[Path] | None = None
        self.frames = 0  # frames recorded
        self.fired = 0  # rule events fired

    def __enter__(self) -> StreamSession:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    def step(self, frame: Frame) -> StreamResult:
        """Run one frame through the whole order and record it.

        Raises `StreamWriteError` (an `OSError`) with the original one-sentence
        message when an event frame, the JSONL or the .mp4 cannot be written.
        An `OSError` from anything else -- the detector, the tracker, drawing,
        a handler -- propagates as it is.
        """
        cfg = self._cfg
        self._ticks.append(time.perf_counter())
        detections = self._tracker.update(frame, self._detector(frame))
        drawn, near_miss, target, status, canvas = self._render(frame, detections, new_frame=True)

        fired = []
        for event in self._engine.update(frame.time, drawn):
            self.fired += 1
            fired.append(event)
            self._act(event, frame, canvas)

        with _writing():
            if self._writer is None:
                # Named after the first frame, so a bare `0` still writes camera_0.
                height, width = frame.image.shape[:2]
                self._writer = output.StreamWriter(
                    frame.source, cfg, self._fps_in, self._frame_size or (width, height),
                    self._is_video,
                )
            self._writer.write(frame, drawn, near_miss, target, canvas)
        self.frames += 1

        self._last = (frame, detections)
        return StreamResult(
            canvas=canvas, drawn=drawn, near_miss=near_miss, target=target,
            events=tuple(fired), status=status,
        )

    def redraw(self) -> StreamResult:
        """Draw the last frame again under the current config and target lock.

        Its tracked detections are split under the current threshold, coloured
        if asked, and the target is chosen again -- a click since the frame
        shows at once. The detector is not called, no rule runs and nothing is
        written: `frames`, `fired` and the files stay as they are. It is the
        same frame again, so it never counts toward releasing a lock whose
        target is absent -- however long a video stays paused. Raises
        `RuntimeError` before the first `step`.
        """
        if self._last is None:
            raise RuntimeError("no frame to redraw yet")
        frame, detections = self._last
        drawn, near_miss, target, status, canvas = self._render(frame, detections, new_frame=False)
        return StreamResult(
            canvas=canvas, drawn=drawn, near_miss=near_miss, target=target,
            events=(), status=status,
        )

    def _render(
        self, frame: Frame, detections: list[Detection], new_frame: bool
    ) -> tuple[list[Detection], list[Detection], TargetState, str, np.ndarray]:
        """Split, colour, choose the target, build the status line and draw one frame.

        `new_frame` is False when the frame was rendered before: the target is
        chosen again without counting a frame toward a lock's release.
        """
        cfg = self._cfg
        drawn = [item for item in detections if not is_debug(item, cfg)]
        near_miss = [item for item in detections if is_debug(item, cfg)]
        if self._want_color:
            drawn = _add_colors(frame, drawn)
        height, width = frame.image.shape[:2]
        target = self._targeting.choose(drawn, (width, height), new_frame=new_frame)
        status = _status(target, self.fps)
        canvas = draw.annotate(frame.image, drawn, cfg, target, status)
        self._on_screen = drawn
        return drawn, near_miss, target, status, canvas

    @property
    def fps(self) -> float:
        """Frames per second over the last frames stepped, 0 until there are two."""
        return _fps(self._ticks)

    def click(self, point: tuple[float, float]) -> None:
        """Lock onto the tracked box under `point` on the last frame, or release."""
        self._targeting.click(point, self._on_screen)

    def retune(self, cfg: Config, want_color: bool) -> None:
        """Use `cfg` and `want_color` from the next frame on, keeping every track.

        The threshold moves ByteTrack's bands with it, so an object drawn at
        the new threshold can also start a track. The files already open keep
        the config they were opened with.
        """
        self._cfg = cfg
        self._want_color = want_color
        self._tracker.set_conf(cfg.model.conf)

    def set_detector(self, detector: Callable[[Frame], list[Detection]]) -> None:
        """Run the next frame through `detector`; tracks, target and rules stay."""
        self._detector = detector

    def close(self) -> list[Path]:
        """Close the stream's files and return their paths. Idempotent."""
        if self._paths is None:
            self._paths = self._writer.close() if self._writer is not None else []
        return list(self._paths)

    def _act(self, event: Event, frame: Frame, canvas: np.ndarray) -> None:
        """Carry out one rule event's actions, in the order the rule lists them."""
        for action in event.actions:
            if action == "log":
                self._on_log(event)
            elif action == "save_frame":
                with _writing():
                    output.write_event_frame(event, frame.source, frame.index, canvas, self._cfg)
            elif isinstance(action, tuple) and action[0] == CALL:
                events.call(action[1], event.detection)


@contextmanager
def _writing() -> Iterator[None]:
    """Turn an `OSError` from a stream's file write into `StreamWriteError`."""
    try:
        yield
    except StreamWriteError:
        raise
    except OSError as err:
        raise StreamWriteError(str(err)) from err


def _fps(ticks: deque[float]) -> float:
    """Frames per second over the last `_FPS_WINDOW` frames, 0 until there are two."""
    if len(ticks) < 2 or ticks[-1] <= ticks[0]:
        return 0.0
    return (len(ticks) - 1) / (ticks[-1] - ticks[0])


def _status(target: TargetState, fps: float) -> str:
    """The line at the top of the overlay: the target, its arrow, and the FPS."""
    rate = f"{fps:.1f} FPS"
    if target.lost:
        return f"target: lost  {rate}"
    detection = target.detection
    if detection is None:
        return f"target: none  {rate}"
    arrow = aim.aim(detection.dx, detection.dy)  # the servo seam: once a frame, target only
    return (
        f"target #{detection.track_id} {detection.cls_name}  "
        f"dx {detection.dx:+d} dy {detection.dy:+d}  {arrow}  {rate}"
    )

