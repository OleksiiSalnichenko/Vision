"""Seam 3: Detector.__init__ refuses to start when the weights file is absent.

This is the offline trap the brief names first: Ultralytics silently downloads
weights when it is handed a bare name, so the file must be checked before
anything in `ultralytics` is touched. These tests must never load a model and
must never reach the network.
"""

import sys
import types
from pathlib import Path

import pytest

from core.config import load_config
from core.detector import Detector

MISSING_WEIGHTS_MESSAGE = "run scripts/fetch_models.py first"

CONFIG_TEMPLATE = """
model:
  weights: {weights}
  imgsz: 640
  conf: 0.5
  conf_debug: 0.25

classes:
  - person

display:
  show_labels: true
  show_offsets: true
  crosshair: true
  center_line: false

output:
  save_json: true
  save_image: true
  dir: out

capture:
  width: 1280
  height: 720
  camera: 0
  count: 5
  interval: 1.0

bench:
  runs: 10
  warmup: 3
"""


def config_pointing_at(tmp_path: Path, weights: str):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG_TEMPLATE.format(weights=weights), encoding="utf-8")
    return load_config(path)


def test_missing_weights_file_fails_with_the_documented_message(tmp_path):
    cfg = config_pointing_at(tmp_path, str(tmp_path / "nowhere" / "yolo26n.pt"))

    with pytest.raises(FileNotFoundError) as failure:
        Detector(cfg)

    assert MISSING_WEIGHTS_MESSAGE in str(failure.value)


def test_missing_weights_never_reaches_the_model(tmp_path, monkeypatch):
    """The point of the check: nothing is loaded, so nothing can be downloaded.

    `ultralytics` is replaced by a stand-in that refuses to be used. If the
    weights check ever moves below the model load, this test says so instead of
    the machine quietly downloading a file it was told not to fetch.
    """
    trap = types.ModuleType("ultralytics")
    trap.YOLO = _refuse
    monkeypatch.setitem(sys.modules, "ultralytics", trap)

    cfg = config_pointing_at(tmp_path, str(tmp_path / "nowhere" / "yolo26n.pt"))

    with pytest.raises(FileNotFoundError):
        Detector(cfg)


def _refuse(*args, **kwargs):
    raise AssertionError("YOLO must not be touched when the weights file is missing")
