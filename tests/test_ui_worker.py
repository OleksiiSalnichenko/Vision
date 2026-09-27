"""The pipeline worker, offscreen, with a stub model and stub sources.

No test here loads a model or opens a camera: the detector factory and the
source factory are stand-ins, and the "camera" is a generator. Most tests
drive the worker on the test's own thread, where its frame ticks run on the
qtbot event loop; the thread tests move it onto a `QThread` and always join it.
"""

from __future__ import annotations

import os

# Before the first Qt import: never a window on the user's screen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Q_ARG, QMetaObject, QThread, Qt

import detect
import core.draw
import core.pipeline
from core import events, output
from core.config import load_config
from core.detector import MISSING_EXPORT_MESSAGE, MISSING_WEIGHTS_MESSAGE, Detector
from core.types import Detection, Frame
from ui.worker import FramePayload, PipelineWorker

CONF = 0.5
CONF_DEBUG = 0.25
FRAME_W, FRAME_H = 80, 60
FPS = 10.0
TIMEOUT_MS = 5000
NAMES = {0: "person", 1: "bottle", 2: "cell phone"}


def detection(cls_name: str, conf: float, bbox, dx: int, dy: int) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(
        cls_id=0, cls_name=cls_name, conf=conf, bbox=bbox,
        center=((x1 + x2) // 2, (y1 + y2) // 2), dx=dx, dy=dy,
        dx_pct=dx / (FRAME_W / 2), dy_pct=dy / (FRAME_H / 2),
    )


# Near the centre, so it is the target until something else is clicked.
PERSON = detection("person", 0.90, (10.0, 10.0, 30.0, 30.0), -20, -10)
# Below CONF, above CONF_DEBUG: a near-miss until the threshold drops.
BOTTLE = detection("bottle", 0.30, (50.0, 30.0, 70.0, 50.0), 20, 10)
# Farther from the centre than PERSON: a target only when clicked.
OTHER = detection("person", 0.80, (52.0, 36.0, 76.0, 56.0), 24, 16)


class StubDetector:
    """Stands in for `Detector`: a fixed list per call, class names, calls counted."""

    def __init__(self, detections) -> None:
        self.detections = list(detections)
        self.calls = 0
        self.classes: list[list[str]] = []

    @property
    def names(self) -> dict[int, str]:
        return dict(NAMES)

    def set_classes(self, classes: list[str]) -> None:
        unknown = [name for name in classes if name not in NAMES.values()]
        if unknown:
            raise ValueError(f"unknown class names in config: {unknown}")
        self.classes.append(list(classes))

    def __call__(self, frame: Frame) -> list[Detection]:
        self.calls += 1
        return list(self.detections)


class DetectorFactory:
    """Hands out the given detectors in turn and remembers every config it got."""

    def __init__(self, *detectors) -> None:
        self._detectors = list(detectors)
        self.configs = []

    def __call__(self, cfg):
        self.configs.append(cfg)
        item = self._detectors.pop(0) if len(self._detectors) > 1 else self._detectors[0]
        if isinstance(item, Exception):
            raise item
        return item


class FakeSource:
    """A `Source` stand-in: fixed frames, or an endless camera; counts `close()`."""

    def __init__(self, frames, *, is_stream=False, is_camera=False, fail_after=None) -> None:
        self._frames = list(frames)
        self.is_stream = is_stream
        self.is_camera = is_camera
        self.fps = FPS if is_stream else 0.0
        self.frame_size = (FRAME_W, FRAME_H) if is_stream else None
        self._fail_after = fail_after
        self.closed = 0

    def __len__(self) -> int:
        return 0 if self.is_camera else len(self._frames)

    def __iter__(self):
        if not self.is_camera:
            yield from self._frames
            return
        index = 0
        while not self.closed:
            if self._fail_after is not None and index >= self._fail_after:
                raise OSError("camera 7 stopped delivering frames")
            yield frame(index, "camera:7")
            index += 1

    def close(self) -> None:
        self.closed += 1


class SourceFactory:
    def __init__(self, sources: dict) -> None:
        self._sources = sources
        self.specs: list[str] = []

    def __call__(self, spec, cfg):
        self.specs.append(spec)
        return self._sources[spec]


def frame(index: int, source: str) -> Frame:
    return Frame(
        image=np.zeros((FRAME_H, FRAME_W, 3), np.uint8),
        source=source, index=index, time=index / FPS,
    )


LOG_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [log]
"""


@pytest.fixture(autouse=True)
def empty_event_bus():
    events.clear()
    yield
    events.clear()


@pytest.fixture
def out_dir(tmp_path) -> Path:
    return tmp_path / "out"


@pytest.fixture
def cfg(tmp_path, write_config, out_dir):
    weights = tmp_path / "stub.pt"
    weights.write_bytes(b"weights")
    rules = tmp_path / "rules.yaml"
    rules.write_text(LOG_RULES, encoding="utf-8")
    return load_config(write_config({
        "model.weights": weights.as_posix(),
        "model.conf": CONF,
        "model.conf_debug": CONF_DEBUG,
        "classes": [],
        "display.color": False,
        "output.save_json": True,
        "output.save_image": True,
        "output.dir": out_dir.as_posix(),
        "rules.file": rules.as_posix(),
    }))


class Recorder:
    """Every signal of one worker, in the order it came."""

    def __init__(self, worker: PipelineWorker, acknowledge: bool = True) -> None:
        self.frames: list[FramePayload] = []
        self.events: list[str] = []
        self.failed: list[str] = []
        self.finished: list[str] = []
        self.model_ready: list[dict] = []
        self.model_failed: list[str] = []
        self.applied: list = []
        worker.frame_ready.connect(self.frames.append)
        worker.event.connect(self.events.append)
        worker.failed.connect(self.failed.append)
        worker.finished.connect(self.finished.append)
        worker.model_ready.connect(self.model_ready.append)
        worker.model_failed.connect(self.model_failed.append)
        worker.applied.connect(self.applied.append)
        if acknowledge:
            # As the window does: every frame taken is said back, so the next one comes.
            worker.frame_ready.connect(worker.frame_shown)


@pytest.fixture
def make_worker(qtbot):
    """Build a worker on the test's thread and make sure it is stopped afterwards."""
    made = []

    def build(cfg, detector_factory, source_factory, acknowledge=True):
        worker = PipelineWorker(cfg, detector_factory, source_factory)
        made.append(worker)
        return worker, Recorder(worker, acknowledge)

    yield build
    for worker in made:
        worker.stop()


@pytest.fixture
def clip(tmp_path) -> str:
    """A spec `is_stream_spec` takes for a video file: an existing `.mp4` path."""
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"")
    return str(path)


def photo_sources(tmp_path, count: int):
    folder = tmp_path / "photos"
    frames = [frame(index, str(folder / f"p{index}.jpg")) for index in range(count)]
    return FakeSource(frames)


def video_source(count: int) -> FakeSource:
    return FakeSource([frame(index, "clip.mp4") for index in range(count)], is_stream=True)


# --- the model ------------------------------------------------------------------


def test_load_model_reports_the_class_names(cfg, make_worker):
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([])), SourceFactory({}))
    worker.load_model()
    assert seen.model_ready == [NAMES]
    assert seen.model_failed == []


@pytest.mark.parametrize(
    ("weights", "message"),
    [("missing/none.pt", MISSING_WEIGHTS_MESSAGE),
     ("missing/none_openvino_model", MISSING_EXPORT_MESSAGE)],
)
def test_missing_weights_is_model_failed_with_the_exact_sentence(
    cfg, make_worker, tmp_path, weights, message
):
    # The real Detector: it checks the disk before ultralytics is imported.
    absent = dataclasses.replace(
        cfg, model=dataclasses.replace(cfg.model, weights=(tmp_path / weights).as_posix())
    )
    worker, seen = make_worker(absent, Detector, SourceFactory({}))
    worker.load_model()
    assert seen.model_failed == [message]
    assert seen.model_ready == []


# --- photos and folders ------------------------------------------------------------


def test_a_photo_is_drawn_saved_and_emitted(cfg, make_worker, tmp_path, out_dir):
    heard = []
    events.on_detect()(heard.append)
    source = photo_sources(tmp_path, 1)
    detector = StubDetector([PERSON, BOTTLE])
    worker, seen = make_worker(cfg, DetectorFactory(detector), SourceFactory({"p": source}))
    worker.load_model()
    worker.open_source("p")

    [payload] = seen.frames
    assert [d.cls_name for d in payload.drawn] == ["person"]
    assert payload.near_miss_count == 1
    assert (payload.index, payload.total, payload.is_stream) == (0, 1, False)
    assert payload.target_track_id is None
    assert sorted(p.name for p in out_dir.iterdir()) == ["p0.json", "p0_annotated.jpg"]
    assert heard == [PERSON]
    assert seen.failed == []


def test_a_folder_goes_back_without_running_the_model_again(cfg, make_worker, tmp_path):
    source = photo_sources(tmp_path, 3)
    detector = StubDetector([PERSON])
    worker, seen = make_worker(cfg, DetectorFactory(detector), SourceFactory({"f": source}))
    worker.load_model()
    worker.open_source("f")
    worker.show_index(1)
    assert detector.calls == 2
    worker.show_index(0)

    assert detector.calls == 2
    assert [(p.index, p.total) for p in seen.frames] == [(0, 3), (1, 3), (0, 3)]


def test_the_payload_shares_no_memory_with_the_worker(cfg, make_worker, tmp_path, monkeypatch):
    canvases = []

    def annotate(image, detections, cfg, target=None, status=None):
        canvases.append(np.full_like(image, 7))  # the array the pipeline keeps
        return canvases[-1]

    monkeypatch.setattr(core.draw, "annotate", annotate)
    source = photo_sources(tmp_path, 1)
    worker, seen = make_worker(
        cfg, DetectorFactory(StubDetector([PERSON])), SourceFactory({"p": source})
    )
    worker.load_model()
    worker.open_source("p")
    worker.set_conf(0.28)  # a redraw of the same photo, from the cache

    for payload, kept in zip(seen.frames, canvases, strict=True):
        assert np.array_equal(payload.canvas, kept)
        assert not np.shares_memory(payload.canvas, kept)
    # The cached detections are the detector's own objects; the payload's are not.
    assert all(d is not PERSON for payload in seen.frames for d in payload.drawn)
    seen.frames[-1].drawn[0].conf = 0.01
    worker.show_index(0)
    assert seen.frames[-1].drawn[0].conf == PERSON.conf


# --- a video file ---------------------------------------------------------------------


def test_a_video_runs_to_the_end_with_events_and_a_summary(
    cfg, make_worker, qtbot, out_dir, clip
):
    source = video_source(4)
    worker, seen = make_worker(
        cfg, DetectorFactory(StubDetector([PERSON, BOTTLE])), SourceFactory({clip: source})
    )
    worker.load_model()
    with qtbot.waitSignal(worker.finished, timeout=TIMEOUT_MS):
        worker.open_source(clip)

    assert [p.index for p in seen.frames] == [0, 1, 2, 3]
    assert all(p.is_stream and p.total == 4 for p in seen.frames)
    assert seen.frames[-1].target_track_id is not None
    # The line output.print_event prints: confirmed on the second frame, t = 0.1 s.
    [line] = seen.events
    assert line.startswith("[00:00.1] person_appeared  person #")
    assert line.endswith(" 0.90  dx -20 dy -10")
    [summary] = seen.finished
    assert summary.startswith("4 frames, 1 events, wrote ")
    assert str(out_dir / "clip.jsonl") in summary
    assert source.closed == 1
    assert seen.failed == []


def test_an_unshown_frame_holds_back_the_next_but_every_frame_is_written(
    cfg, make_worker, qtbot, out_dir, clip
):
    count = 40
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON])),
                               SourceFactory({clip: video_source(count)}), acknowledge=False)
    worker.load_model()
    with qtbot.waitSignal(worker.finished, timeout=TIMEOUT_MS):
        worker.open_source(clip)

    # Never acknowledged: the first frame, and at the end only the last one.
    assert [p.index for p in seen.frames] == [0, count - 1]
    [summary] = seen.finished
    assert summary.startswith(f"{count} frames, 1 events, wrote ")
    assert len((out_dir / "clip.jsonl").read_text(encoding="utf-8").splitlines()) == count
    assert len(seen.events) == 1  # the rules saw every frame


def test_acknowledging_a_frame_brings_the_newest_one(cfg, make_worker, qtbot, clip):
    detector = StubDetector([PERSON])
    worker, seen = make_worker(cfg, DetectorFactory(detector),
                               SourceFactory({clip: video_source(10_000)}), acknowledge=False)
    worker.load_model()
    worker.open_source(clip)
    qtbot.waitUntil(lambda: detector.calls >= 5, timeout=TIMEOUT_MS)
    assert len(seen.frames) == 1

    worker.frame_shown()

    assert len(seen.frames) == 2
    assert seen.frames[1].index == detector.calls - 1  # the newest, not the second


# --- a camera: stop, switch, failure --------------------------------------------------

CAMERA = "camera:7"


def camera_source(**kwargs) -> FakeSource:
    return FakeSource([], is_stream=True, is_camera=True, **kwargs)


def test_stop_closes_the_camera_and_says_the_summary(cfg, make_worker, qtbot):
    camera = camera_source()
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON])),
                               SourceFactory({CAMERA: camera}))
    worker.load_model()
    worker.open_source(CAMERA)
    qtbot.waitUntil(lambda: len(seen.frames) >= 3, timeout=TIMEOUT_MS)
    worker.stop()
    shown = len(seen.frames)
    qtbot.wait(50)

    assert camera.closed == 1
    assert len(seen.frames) == shown  # no frame after the stop
    [summary] = seen.finished
    assert summary.startswith(f"{shown} frames, ")
    assert all(p.total == 0 for p in seen.frames)  # a camera's length is unknown


def test_opening_another_source_releases_the_camera_first(cfg, make_worker, qtbot, tmp_path):
    camera = camera_source()
    photo = photo_sources(tmp_path, 1)
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON])),
                               SourceFactory({CAMERA: camera, "p": photo}))
    worker.load_model()
    worker.open_source(CAMERA)
    qtbot.waitUntil(lambda: len(seen.frames) >= 2, timeout=TIMEOUT_MS)
    worker.open_source("p")
    qtbot.wait(50)

    assert camera.closed == 1
    assert len(seen.finished) == 1
    assert seen.frames[-1].is_stream is False


def test_a_camera_that_stops_delivering_fails_and_finishes(cfg, make_worker, qtbot):
    camera = camera_source(fail_after=3)
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON])),
                               SourceFactory({CAMERA: camera}))
    worker.load_model()
    with qtbot.waitSignal(worker.finished, timeout=TIMEOUT_MS):
        worker.open_source(CAMERA)

    assert seen.failed == ["camera 7 stopped delivering frames"]
    assert seen.finished[0].startswith("3 frames, ")
    assert camera.closed == 1


def test_a_file_that_cannot_be_written_fails_and_finishes(cfg, make_worker, qtbot, monkeypatch):
    def refuse(self, *args, **kwargs):
        raise OSError("could not write: clip.jsonl")

    monkeypatch.setattr(output.StreamWriter, "write", refuse)
    camera = camera_source()
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON])),
                               SourceFactory({CAMERA: camera}))
    worker.load_model()
    with qtbot.waitSignal(worker.finished, timeout=TIMEOUT_MS):
        worker.open_source(CAMERA)

    assert seen.failed == ["could not write: clip.jsonl"]
    assert seen.finished[0].startswith("0 frames, ")
    assert camera.closed == 1


def test_a_stream_that_cannot_start_closes_its_source_and_fails(
    cfg, make_worker, monkeypatch
):
    def broken_tracker(cfg):
        raise ImportError("no module named 'lap'")

    monkeypatch.setattr(core.pipeline, "Tracker", broken_tracker)
    camera = camera_source()
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON])),
                               SourceFactory({CAMERA: camera}))
    worker.load_model()
    worker.open_source(CAMERA)

    assert seen.failed == ["no module named 'lap'"]
    assert camera.closed == 1
    assert seen.frames == []


# --- checks before the source opens ---------------------------------------------------

DEBOUNCE = "debounce: {confirm_frames: 2, cooldown: 1.0}\n"


def test_a_broken_rules_file_never_opens_the_camera(cfg, make_worker):
    Path(cfg.rules.file).write_text(
        DEBOUNCE + "rules: [ {name: x, when: never} ]\n", encoding="utf-8"
    )
    sources = SourceFactory({CAMERA: camera_source()})
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([])), sources)
    worker.load_model()
    worker.open_source(CAMERA)

    assert len(seen.failed) == 1 and "rules[x].when" in seen.failed[0]
    assert sources.specs == []


def test_an_unknown_handler_never_opens_the_camera(cfg, make_worker, tmp_path, monkeypatch):
    Path(cfg.rules.file).write_text(
        DEBOUNCE + "rules:\n  - {name: r, when: appeared, do: [{call: nope}]}\n",
        encoding="utf-8",
    )
    handlers = tmp_path / "handlers.py"
    handlers.write_text("", encoding="utf-8")
    monkeypatch.setattr(detect, "HANDLERS_PATH", handlers)
    sources = SourceFactory({CAMERA: camera_source()})
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([])), sources)
    worker.load_model()
    worker.open_source(CAMERA)

    assert seen.failed == ["unknown handler in rules.yaml: nope"]
    assert sources.specs == []


def test_missing_weights_never_open_the_camera(cfg, make_worker):
    sources = SourceFactory({CAMERA: camera_source()})
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([])), sources)
    worker.load_model()
    Path(cfg.model.weights).unlink()
    worker.open_source(CAMERA)

    assert seen.failed == [MISSING_WEIGHTS_MESSAGE]
    assert sources.specs == []


# --- the threshold ---------------------------------------------------------------------


def debug_flags(path: Path) -> dict[str, bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["cls_name"]: item["debug"] for item in data["detections"]}


def test_set_conf_redraws_a_photo_and_commit_rewrites_its_json(
    cfg, make_worker, tmp_path, out_dir
):
    detector = StubDetector([PERSON, BOTTLE])
    worker, seen = make_worker(cfg, DetectorFactory(detector),
                               SourceFactory({"p": photo_sources(tmp_path, 1)}))
    worker.load_model()
    worker.open_source("p")
    worker.set_conf(0.28)

    assert detector.calls == 1
    assert [d.cls_name for d in seen.frames[-1].drawn] == ["person", "bottle"]
    assert seen.frames[-1].near_miss_count == 0
    assert debug_flags(out_dir / "p0.json") == {"person": False, "bottle": True}
    worker.commit_still()
    assert debug_flags(out_dir / "p0.json") == {"person": False, "bottle": False}


def test_set_conf_on_a_stream_applies_from_the_next_frame(cfg, make_worker, qtbot):
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON, BOTTLE])),
                               SourceFactory({CAMERA: camera_source()}))
    worker.load_model()
    worker.open_source(CAMERA)
    qtbot.waitUntil(lambda: len(seen.frames) >= 3, timeout=TIMEOUT_MS)
    assert seen.frames[-1].near_miss_count == 1
    before = len(seen.frames)
    worker.set_conf(0.28)
    qtbot.waitUntil(lambda: len(seen.frames) >= before + 3, timeout=TIMEOUT_MS)

    last = seen.frames[-1]
    assert last.near_miss_count == 0
    assert {d.cls_name: d.track_id is not None for d in last.drawn} == {
        "person": True, "bottle": True,  # ByteTrack's bands moved with it
    }


# --- settings ---------------------------------------------------------------------------


def test_apply_new_classes_goes_to_the_loaded_model(cfg, make_worker, tmp_path):
    detector = StubDetector([PERSON])
    factory = DetectorFactory(detector)
    worker, seen = make_worker(cfg, factory, SourceFactory({"p": photo_sources(tmp_path, 1)}))
    worker.load_model()
    worker.open_source("p")
    worker.apply(dataclasses.replace(cfg, classes=["person"]))

    assert detector.classes == [["person"]]
    assert len(factory.configs) == 1
    assert seen.applied[-1].classes == ["person"]
    assert detector.calls == 2  # the photo is detected again under the new classes


def test_apply_an_unknown_class_keeps_the_old_classes(cfg, make_worker):
    detector = StubDetector([])
    worker, seen = make_worker(cfg, DetectorFactory(detector), SourceFactory({}))
    worker.load_model()
    worker.apply(dataclasses.replace(cfg, classes=["unicorn"]))

    assert len(seen.failed) == 1 and seen.failed[0].startswith("unknown class names in config")
    assert seen.applied[-1].classes == cfg.classes
    assert detector.classes == []


def test_apply_keeps_the_threshold_set_by_the_slider(cfg, make_worker):
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([])), SourceFactory({}))
    worker.load_model()
    worker.set_conf(0.4)
    worker.apply(dataclasses.replace(
        cfg, display=dataclasses.replace(cfg.display, center_line=not cfg.display.center_line)
    ))
    assert seen.applied[-1].model.conf == 0.4
    assert seen.applied[-1].display.center_line is not cfg.display.center_line


def other_weights(cfg, tmp_path):
    weights = tmp_path / "other.pt"
    weights.write_bytes(b"weights")
    return dataclasses.replace(cfg, model=dataclasses.replace(cfg.model, weights=weights.as_posix()))


def test_apply_a_new_model_on_a_stream_keeps_the_tracks(cfg, make_worker, qtbot, tmp_path):
    old, new = StubDetector([PERSON]), StubDetector([PERSON])
    factory = DetectorFactory(old, new)
    worker, seen = make_worker(cfg, factory, SourceFactory({CAMERA: camera_source()}))
    worker.load_model()
    worker.open_source(CAMERA)
    qtbot.waitUntil(lambda: len(seen.frames) >= 3, timeout=TIMEOUT_MS)
    track_id = seen.frames[-1].drawn[0].track_id
    assert track_id is not None
    worker.apply(other_weights(cfg, tmp_path))
    before = len(seen.frames)
    qtbot.waitUntil(lambda: len(seen.frames) >= before + 2, timeout=TIMEOUT_MS)

    assert len(factory.configs) == 2
    assert new.calls >= 2
    assert seen.frames[-1].drawn[0].track_id == track_id
    assert len(seen.model_ready) == 2


def test_apply_a_model_that_will_not_load_keeps_the_old_one(cfg, make_worker, tmp_path):
    old = StubDetector([PERSON])
    factory = DetectorFactory(old, FileNotFoundError(MISSING_WEIGHTS_MESSAGE))
    worker, seen = make_worker(cfg, factory, SourceFactory({"p": photo_sources(tmp_path, 1)}))
    worker.load_model()
    worker.apply(other_weights(cfg, tmp_path))
    worker.open_source("p")

    assert seen.model_failed == [MISSING_WEIGHTS_MESSAGE]
    assert seen.applied[-1].model.weights == cfg.model.weights
    assert old.calls == 1  # the photo ran on the old model


# --- pause and click ---------------------------------------------------------------------


def test_a_paused_video_holds_and_a_click_still_picks_the_target(
    cfg, make_worker, qtbot, clip
):
    worker, seen = make_worker(cfg, DetectorFactory(StubDetector([PERSON, OTHER])),
                               SourceFactory({clip: video_source(200)}))
    worker.load_model()
    worker.open_source(clip)
    qtbot.waitUntil(lambda: len(seen.frames) >= 3, timeout=TIMEOUT_MS)
    ids = {d.bbox: d.track_id for d in seen.frames[-1].drawn}
    assert seen.frames[-1].target_track_id == ids[PERSON.bbox]  # nearest the centre

    worker.set_paused(True)
    held = len(seen.frames)
    qtbot.wait(100)
    assert len(seen.frames) == held

    worker.click(64.0, 46.0)  # inside OTHER only
    # Shown at once, on the frame that is held: same index, new target.
    assert len(seen.frames) == held + 1
    assert seen.frames[-1].index == seen.frames[-2].index
    assert seen.frames[-1].target_track_id == ids[OTHER.bbox]

    worker.set_paused(False)
    qtbot.waitUntil(lambda: len(seen.frames) >= held + 3, timeout=TIMEOUT_MS)
    assert seen.frames[-1].target_track_id == ids[OTHER.bbox]
    indices = [p.index for p in seen.frames]
    assert indices == list(range(held)) + list(range(held - 1, len(indices) - 1))  # one chain


def test_a_paused_video_redraws_under_a_new_threshold(cfg, make_worker, qtbot, clip):
    detector = StubDetector([PERSON, BOTTLE])
    worker, seen = make_worker(cfg, DetectorFactory(detector),
                               SourceFactory({clip: video_source(200)}))
    worker.load_model()
    worker.open_source(clip)
    qtbot.waitUntil(lambda: len(seen.frames) >= 3, timeout=TIMEOUT_MS)
    worker.set_paused(True)
    held, calls = len(seen.frames), detector.calls
    worker.set_conf(0.28)

    assert len(seen.frames) == held + 1
    assert sorted(d.cls_name for d in seen.frames[-1].drawn) == ["bottle", "person"]
    assert seen.frames[-1].near_miss_count == 0
    assert detector.calls == calls


# --- on its own thread ---------------------------------------------------------------------


def test_on_a_thread_shutdown_releases_the_camera_and_ends_the_thread(cfg, qtbot):
    camera = camera_source()
    worker = PipelineWorker(cfg, DetectorFactory(StubDetector([PERSON])),
                            SourceFactory({CAMERA: camera}))
    seen = Recorder(worker)
    thread = QThread()
    worker.moveToThread(thread)
    thread.start()
    try:
        QMetaObject.invokeMethod(worker, "load_model", Qt.QueuedConnection)
        QMetaObject.invokeMethod(worker, "open_source", Qt.QueuedConnection,
                                 Q_ARG(str, CAMERA))
        qtbot.waitUntil(lambda: len(seen.frames) >= 3, timeout=TIMEOUT_MS)
        QMetaObject.invokeMethod(worker, "shutdown", Qt.QueuedConnection)
        assert thread.wait(TIMEOUT_MS)
    finally:
        if thread.isRunning():
            thread.quit()
            thread.wait(TIMEOUT_MS)

    assert camera.closed == 1
    assert len(seen.finished) == 1
