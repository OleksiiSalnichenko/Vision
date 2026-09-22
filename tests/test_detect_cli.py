"""The wiring `detect.py` owns: the drawn / near-miss split and the two thresholds.

`Detector` hands back one list holding everything from `conf_debug` upwards,
and `detect.py` is the only place that splits it. `core.draw` and `core.output`
are handed ready-made lists and know no threshold at all, so nothing but these
assertions would notice a near-miss starting to be drawn and printed.

No model is loaded here: the detector is a stand-in that returns a fixed list,
which is all `process` asks of it. The thresholds below are the shipped ones
from the spec -- draw and print at `conf` 0.5, keep down to `conf_debug` 0.25.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

import detect
from core import events
from core.config import load_config
from core.types import Detection, Frame

CONF = 0.5
CONF_DEBUG = 0.25


@pytest.fixture
def cfg(tmp_path, write_config):
    """The shipped thresholds, with the output written into `tmp_path`."""
    return load_config(
        write_config(
            {
                "model.conf": CONF,
                "model.conf_debug": CONF_DEBUG,
                "output.save_json": True,
                "output.save_image": False,
                "output.dir": tmp_path.as_posix(),
            }
        )
    )


class StubDetector:
    """Stands in for `Detector`: one call, one fixed list, no weights."""

    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def __call__(self, frame: Frame) -> list[Detection]:
        return list(self._detections)


def detection(cls_name: str, conf: float) -> Detection:
    return Detection(
        cls_id=0,
        cls_name=cls_name,
        conf=conf,
        bbox=(10.0, 10.0, 30.0, 30.0),
        center=(20, 20),
        dx=-20,
        dy=-10,
        dx_pct=-0.5,
        dy_pct=-0.33,
    )


def flags(**overrides) -> argparse.Namespace:
    """The parsed command line, with everything not named left unset."""
    return argparse.Namespace(**{"conf": None, "classes": None, **overrides})


def test_only_detections_at_or_above_conf_are_drawn_printed_and_marked(
    cfg, tmp_path, capsys, monkeypatch
):
    # Exactly at the threshold counts as drawn: the spec says "at or above".
    sure = detection("person", CONF)
    near_miss = detection("bottle", 0.30)
    handed_to_annotate = []
    monkeypatch.setattr(
        detect.draw,
        "annotate",
        lambda image, detections, config: handed_to_annotate.append(list(detections))
        or image,
    )
    frame = Frame(image=np.zeros((60, 80, 3), np.uint8), source="photo.jpg", index=0)

    detect.process(frame, StubDetector([sure, near_miss]), cfg, want_color=False)

    printed = capsys.readouterr().out
    assert handed_to_annotate == [[sure]]
    assert "person" in printed
    assert "bottle" not in printed  # a near miss is never drawn and never printed
    written = json.loads(Path(tmp_path / "photo.json").read_text(encoding="utf-8"))
    assert [(item["cls_name"], item["debug"]) for item in written["detections"]] == [
        ("person", False),
        ("bottle", True),
    ]


def test_conf_flag_below_conf_debug_lowers_the_lower_threshold_too(cfg):
    # The model runs one pass at conf_debug, so a flag under that floor would
    # otherwise show exactly what conf_debug already showed.
    lowered = detect.with_overrides(cfg, flags(conf=0.10))

    assert lowered.model.conf == 0.10
    assert lowered.model.conf_debug == 0.10
    assert cfg.model.conf_debug == CONF_DEBUG  # the loaded config is untouched


def test_conf_flag_above_conf_debug_leaves_the_lower_threshold_alone(cfg):
    raised = detect.with_overrides(cfg, flags(conf=0.70))

    assert raised.model.conf == 0.70
    assert raised.model.conf_debug == CONF_DEBUG


# --- streams ---------------------------------------------------------------
#
# `run_stream` is driven by a stand-in source that yields five synthetic frames
# and says it is a stream. No camera is opened, no window is shown and no model
# is loaded; ByteTrack itself is real, because it is not a model.

FRAMES = 5
FRAME_W, FRAME_H = 80, 60
STREAM_NAME = "clip.mp4"  # not a file on disk: nothing here is a real video

APPEARED_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [log]
"""

CALL_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [{call: greet}]
"""

GREETING_HANDLERS = """
from core.events import on_detect


@on_detect(cls="person")
def greet(detection):
    print(f"greet saw {detection.cls_name}")
"""


class StubSource:
    """Five black frames, 0.1 s apart, from something that calls itself a stream."""

    is_stream = True
    fps = 10.0
    frame_size = (FRAME_W, FRAME_H)

    def __iter__(self):
        for index in range(FRAMES):
            yield Frame(
                image=np.zeros((FRAME_H, FRAME_W, 3), np.uint8),
                source=STREAM_NAME,
                index=index,
                time=index / self.fps,
            )

    def __len__(self) -> int:
        return FRAMES


@pytest.fixture(autouse=True)
def empty_event_bus():
    """The bus is module state; no test may leave a handler behind."""
    events.clear()
    yield
    events.clear()


@pytest.fixture
def stream_cfg(tmp_path, write_config):
    """Returns a config whose rules file holds `rules_text`, output in `tmp_path`."""

    def build(rules_text: str):
        rules = tmp_path / "rules.yaml"
        rules.write_text(rules_text, encoding="utf-8")
        return load_config(
            write_config(
                {
                    "model.conf": CONF,
                    "model.conf_debug": CONF_DEBUG,
                    "classes": [],
                    "output.save_json": True,
                    "output.save_image": False,
                    "output.dir": tmp_path.as_posix(),
                    "rules.file": rules.as_posix(),
                }
            )
        )

    return build


def stream_args() -> argparse.Namespace:
    return argparse.Namespace(source=STREAM_NAME, color=False, no_window=True)


def sure_and_near_miss() -> StubDetector:
    person = detection("person", 0.90)
    bottle = dataclasses.replace(detection("bottle", 0.30), bbox=(50.0, 30.0, 70.0, 50.0))
    return StubDetector([person, bottle])


def run(cfg) -> int:
    return detect.run_stream(
        StubSource(), sure_and_near_miss(), cfg, stream_args(), detect.Window(enabled=False, stream=True)
    )


def test_stream_writes_a_line_per_frame_and_prints_only_events(stream_cfg, tmp_path, capsys):
    heard = []
    events.on_detect()(heard.append)  # a catch-all: emit would reach it

    code = run(stream_cfg(APPEARED_RULES))

    assert code == 0
    lines = (tmp_path / "clip.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == FRAMES
    rows = [json.loads(line) for line in lines]
    assert [row["index"] for row in rows] == list(range(FRAMES))
    for row in rows:
        assert [(d["cls_name"], d["debug"]) for d in row["detections"]] == [
            ("person", False),
            ("bottle", True),
        ]
    printed = capsys.readouterr().out.splitlines()
    assert len([line for line in printed if "person_appeared" in line]) == 1
    assert not any("bottle" in line for line in printed)  # a near miss is never printed
    assert printed[-1].startswith(f"{FRAMES} frames, 1 events, wrote ")
    assert len(printed) == 2  # the event and the summary, nothing per frame
    assert heard == []  # on a stream the bus hears rules only, never emit


def test_a_call_action_runs_the_function_from_the_handlers_file(
    stream_cfg, tmp_path, capsys, monkeypatch
):
    handlers = tmp_path / "handlers.py"
    handlers.write_text(GREETING_HANDLERS, encoding="utf-8")
    monkeypatch.setattr(detect, "HANDLERS_PATH", handlers)

    code = run(stream_cfg(CALL_RULES))

    assert code == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed.count("greet saw person") == 1  # once: the rule fires once per track
    assert events.names() == set()  # the handlers are unhooked when the stream ends


def test_a_call_to_a_function_nobody_registered_stops_the_run(
    stream_cfg, tmp_path, capsys, monkeypatch
):
    handlers = tmp_path / "handlers.py"
    handlers.write_text("# no functions here\n", encoding="utf-8")
    monkeypatch.setattr(detect, "HANDLERS_PATH", handlers)

    code = run(stream_cfg(CALL_RULES))

    assert code == detect.EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.err.strip() == "unknown handler in rules.yaml: greet"
    assert not (tmp_path / "clip.jsonl").exists()  # stopped before the first frame
