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
import json
from pathlib import Path

import numpy as np
import pytest

import detect
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
