"""The shared frame pipeline: the order of one frame, for a photo and a stream.

Driven with a stand-in detector and synthetic frames, as `test_detect_cli`
does: no model, no camera, no window. ByteTrack itself is real, because it is
not a model.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

import core.attributes
import core.output

from core import events, pipeline
from core.config import load_config
from core.types import Detection, Frame

CONF = 0.5
CONF_DEBUG = 0.25
FRAME_W, FRAME_H = 80, 60
FPS = 10.0


class StubDetector:
    """Stands in for `Detector`: a fixed list per call, and a count of calls."""

    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections
        self.calls = 0

    def __call__(self, frame: Frame) -> list[Detection]:
        self.calls += 1
        return list(self._detections)


def detection(cls_name: str, conf: float, bbox=(10.0, 10.0, 30.0, 30.0)) -> Detection:
    return Detection(
        cls_id=0,
        cls_name=cls_name,
        conf=conf,
        bbox=bbox,
        center=(20, 20),
        dx=-20,
        dy=-10,
        dx_pct=-0.5,
        dy_pct=-0.33,
    )


PERSON = detection("person", 0.90)
BOTTLE = detection("bottle", 0.30, bbox=(50.0, 30.0, 70.0, 50.0))


def frame(index: int = 0, source: str = "photo.jpg") -> Frame:
    return Frame(
        image=np.zeros((FRAME_H, FRAME_W, 3), np.uint8),
        source=source,
        index=index,
        time=index / FPS,
    )


@pytest.fixture(autouse=True)
def empty_event_bus():
    events.clear()
    yield
    events.clear()


@pytest.fixture
def config(tmp_path, write_config):
    """Returns a loaded config writing into `out_dir`, with `overrides` on top."""

    def build(out_dir: Path | None = None, **overrides):
        values = {
            "model.conf": CONF,
            "model.conf_debug": CONF_DEBUG,
            "classes": [],
            "display.color": False,
            "output.save_json": True,
            "output.save_image": True,
            "output.dir": (out_dir or tmp_path).as_posix(),
        }
        values.update({key.replace("__", "."): value for key, value in overrides.items()})
        return load_config(write_config(values))

    return build


# --- photos ----------------------------------------------------------------


def test_a_still_is_split_into_drawn_and_near_miss(config):
    result = pipeline.process_still(frame(), StubDetector([PERSON, BOTTLE]), config(), False)

    assert result.drawn == [PERSON]
    assert result.near_miss == [BOTTLE]
    assert result.detections == [PERSON, BOTTLE]
    assert result.canvas.shape == (FRAME_H, FRAME_W, 3)


def test_resplit_under_a_lower_threshold_draws_the_near_miss_without_the_model(config):
    detector = StubDetector([PERSON, BOTTLE])
    first = pipeline.process_still(frame(), detector, config(), False)

    lowered = config(model__conf=0.28)
    again = pipeline.resplit_still(frame(), first.detections, lowered, False)

    assert detector.calls == 1
    assert again.drawn == [PERSON, BOTTLE]
    assert again.near_miss == []
    assert not np.array_equal(again.canvas, first.canvas)  # the bottle box is drawn now


def test_save_still_writes_the_overlay_and_a_json_with_near_misses_marked(config, tmp_path):
    result = pipeline.process_still(frame(), StubDetector([PERSON, BOTTLE]), config(), False)

    paths = pipeline.save_still("photo.jpg", result, config())

    assert paths == [tmp_path / "photo_annotated.jpg", tmp_path / "photo.json"]
    image = cv2.imdecode(np.fromfile(tmp_path / "photo_annotated.jpg", np.uint8), cv2.IMREAD_COLOR)
    assert image.shape == (FRAME_H, FRAME_W, 3)
    written = json.loads((tmp_path / "photo.json").read_text(encoding="utf-8"))
    assert written["source"] == "photo.jpg"
    assert [(d["cls_name"], d["conf"], d["bbox"], d["debug"]) for d in written["detections"]] == [
        ("person", 0.90, [10.0, 10.0, 30.0, 30.0], False),
        ("bottle", 0.30, [50.0, 30.0, 70.0, 50.0], True),
    ]


def test_save_still_names_each_file_as_soon_as_it_is_written(config, tmp_path):
    result = pipeline.process_still(frame(), StubDetector([PERSON]), config(), False)
    seen = []

    pipeline.save_still(
        "photo.jpg", result, config(),
        on_written=lambda path: seen.append((path.name, (tmp_path / "photo.json").exists())),
    )

    assert seen == [("photo_annotated.jpg", False), ("photo.json", True)]


def test_resplit_with_colour_leaves_the_cached_detections_uncoloured(config, monkeypatch):
    monkeypatch.setattr(core.attributes, "dominant_color", lambda image, bbox: "red")
    cached = [dataclasses.replace(PERSON), dataclasses.replace(BOTTLE)]

    again = pipeline.resplit_still(frame(), cached, config(), True)

    assert [d.color for d in again.drawn] == ["red"]
    assert [d.color for d in cached] == [None, None]
    assert [d.color for d in again.detections] == [None, None]


# --- streams ---------------------------------------------------------------

LOG_AND_SAVE_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [log, save_frame]
"""


@pytest.fixture
def rule_set(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(LOG_AND_SAVE_RULES, encoding="utf-8")
    return pipeline.prepare_rules(rules, tmp_path / "no_handlers.py")


def session(detector, cfg, rule_set, logged=None) -> pipeline.StreamSession:
    return pipeline.StreamSession(
        detector, cfg, rule_set, FPS, (FRAME_W, FRAME_H), is_video=False,
        on_log=(logged.append if logged is not None else lambda event: None),
        want_color=False,
    )


def stream_frame(index: int) -> Frame:
    return frame(index, source="clip.mp4")


def test_a_rule_logs_through_the_callback_and_saves_its_frame(
    config, rule_set, tmp_path, capsys
):
    logged = []
    with session(StubDetector([PERSON, BOTTLE]), config(), rule_set, logged) as run:
        results = [run.step(stream_frame(index)) for index in range(4)]
        paths = run.close()

    fired = [event for result in results for event in result.events]
    assert [event.rule for event in fired] == ["person_appeared"]
    assert logged == fired
    assert capsys.readouterr().out == ""  # nothing printed: log is the caller's
    # Tracked from frame 0, confirmed by the second frame: the event is frame 1's.
    assert [path.name for path in (tmp_path / "events").iterdir()] == [
        "clip_person_appeared_1.jpg"
    ]
    assert paths == [tmp_path / "clip.jsonl"]
    assert run.close() == paths  # a second close changes nothing
    assert (run.frames, run.fired) == (4, 1)
    assert [d.cls_name for d in results[-1].drawn] == ["person"]
    assert [d.cls_name for d in results[-1].near_miss] == ["bottle"]


def test_retune_to_a_lower_threshold_draws_and_tracks_the_old_near_miss(config, rule_set):
    cfg = config()
    run = session(StubDetector([PERSON, BOTTLE]), cfg, rule_set)
    before = [run.step(stream_frame(index)) for index in range(3)]
    person_id = before[-1].drawn[0].track_id
    assert person_id is not None
    assert [d.cls_name for d in before[-1].near_miss] == ["bottle"]

    lowered = dataclasses.replace(cfg, model=dataclasses.replace(cfg.model, conf=0.28))
    run.retune(lowered, want_color=False)
    after = [run.step(stream_frame(index)) for index in range(3, 6)]
    run.close()

    drawn = {d.cls_name: d.track_id for d in after[-1].drawn}
    assert set(drawn) == {"person", "bottle"}
    assert after[-1].near_miss == []
    assert drawn["bottle"] is not None  # it can start a track, so it can be a target
    assert drawn["person"] == person_id  # the tracks were not reset


def test_set_detector_runs_the_next_frame_through_the_new_model(config, rule_set):
    old, new = StubDetector([PERSON]), StubDetector([PERSON])
    run = session(old, config(), rule_set)
    first = [run.step(stream_frame(index)) for index in range(2)]

    run.set_detector(new)
    second = run.step(stream_frame(2))
    run.close()

    assert (old.calls, new.calls) == (2, 1)
    assert second.drawn[0].track_id == first[-1].drawn[0].track_id  # tracker kept


def test_retune_brings_colour_and_display_changes_to_the_next_frame(config, rule_set, monkeypatch):
    monkeypatch.setattr(core.attributes, "dominant_color", lambda image, bbox: "red")
    cfg = config(
        display__crosshair=False, display__center_line=False, display__show_offsets=False
    )
    run = session(StubDetector([PERSON]), cfg, rule_set)
    before = run.step(stream_frame(0))

    crosshair = dataclasses.replace(cfg, display=dataclasses.replace(cfg.display, crosshair=True))
    run.retune(crosshair, want_color=True)
    after = run.step(stream_frame(1))
    run.close()

    assert before.drawn[0].color is None
    assert after.drawn[0].color == "red"
    # The centre row right of the person box: clear of the box and the status line.
    arm = (FRAME_H // 2, slice(33, FRAME_W - 5))
    assert not before.canvas[arm].any()
    assert after.canvas[arm].any()  # the crosshair's arm is drawn now


def test_an_unwritable_event_frame_is_a_write_error(config, rule_set, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("could not encode image: clip_person_appeared_1.jpg")

    monkeypatch.setattr(core.output, "write_event_frame", refuse)
    run = session(StubDetector([PERSON]), config(), rule_set)
    run.step(stream_frame(0))

    with pytest.raises(pipeline.StreamWriteError, match="could not encode image"):
        run.step(stream_frame(1))
    run.close()


def test_an_oserror_from_the_detector_is_not_a_write_error(config, rule_set):
    class Broken:
        def __call__(self, frame):
            raise OSError("model file vanished")

    run = session(Broken(), config(), rule_set)

    with pytest.raises(OSError) as raised:
        run.step(stream_frame(0))
    run.close()
    assert not isinstance(raised.value, pipeline.StreamWriteError)


# --- redraw --------------------------------------------------------------------


def _jsonl_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_redraw_before_any_frame_is_an_error(config, rule_set):
    run = session(StubDetector([PERSON]), config(), rule_set)
    with pytest.raises(RuntimeError, match="no frame to redraw"):
        run.redraw()
    run.close()


def test_redraw_after_retune_draws_the_former_near_miss_without_the_model(
    config, rule_set, tmp_path
):
    detector = StubDetector([PERSON, BOTTLE])
    cfg = config()
    run = session(detector, cfg, rule_set)
    for index in range(3):
        run.step(stream_frame(index))
    lines = _jsonl_lines(tmp_path / "clip.jsonl")
    files = sorted(p.name for p in tmp_path.rglob("*"))

    run.retune(dataclasses.replace(cfg, model=dataclasses.replace(cfg.model, conf=0.28)),
               want_color=False)
    again = run.redraw()

    assert sorted(d.cls_name for d in again.drawn) == ["bottle", "person"]
    assert again.near_miss == []
    assert again.events == ()
    assert detector.calls == 3
    assert (run.frames, run.fired) == (3, 1)
    assert _jsonl_lines(tmp_path / "clip.jsonl") == lines
    assert sorted(p.name for p in tmp_path.rglob("*")) == files
    run.close()


OTHER = Detection(
    cls_id=0, cls_name="person", conf=0.80, bbox=(52.0, 36.0, 76.0, 56.0),
    center=(64, 46), dx=24, dy=16, dx_pct=0.6, dy_pct=0.53,
)


def test_redraw_after_a_click_shows_the_new_target(config, rule_set):
    detector = StubDetector([PERSON, OTHER])
    run = session(detector, config(), rule_set)
    for index in range(3):
        last = run.step(stream_frame(index))
    ids = {d.bbox: d.track_id for d in last.drawn}
    assert last.target.detection.track_id == ids[PERSON.bbox]  # nearest the centre

    run.click((64.0, 46.0))  # inside OTHER only
    again = run.redraw()

    assert again.target.detection.track_id == ids[OTHER.bbox]
    assert again.target.locked
    assert detector.calls == 3
    assert not np.array_equal(again.canvas, last.canvas)  # the TARGET box moved
    run.close()


def test_redraws_of_a_held_frame_never_release_the_lock(config, rule_set):
    cfg = config()
    run = session(StubDetector([PERSON, OTHER]), cfg, rule_set)
    for index in range(3):
        last = run.step(stream_frame(index))
    ids = {d.bbox: d.track_id for d in last.drawn}
    run.click((64.0, 46.0))  # lock OTHER
    raised = dataclasses.replace(cfg, model=dataclasses.replace(cfg.model, conf=0.85))

    run.retune(raised, want_color=False)  # OTHER (0.80) is a near-miss now
    for _ in range(cfg.tracker.track_buffer + 3):
        hidden = run.redraw()
        assert hidden.target.detection is None
        assert (hidden.target.locked, hidden.target.lost) == (True, True)

    run.retune(cfg, want_color=False)
    shown = run.redraw()
    run.close()
    assert shown.target.detection.track_id == ids[OTHER.bbox]
    assert shown.target.locked and not shown.target.lost
