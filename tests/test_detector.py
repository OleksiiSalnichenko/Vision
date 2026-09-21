"""Seam 3: Detector.__init__ refuses to start when the weights file is absent.

This is the offline trap the brief names first: Ultralytics silently downloads
weights when it is handed a bare name, so the file must be checked before
anything in `ultralytics` is touched. These tests must never load a model and
must never reach the network.
"""

import sys
import types

import pytest

from core.config import load_config
from core.detector import Detector

MISSING_WEIGHTS_MESSAGE = "run scripts/fetch_models.py first"


def config_pointing_at(write_config, weights: str):
    return load_config(write_config({"model.weights": weights}))


def test_missing_weights_file_fails_with_the_documented_message(tmp_path, write_config):
    cfg = config_pointing_at(write_config, str(tmp_path / "nowhere" / "yolo26n.pt"))

    with pytest.raises(FileNotFoundError) as failure:
        Detector(cfg)

    assert MISSING_WEIGHTS_MESSAGE in str(failure.value)


def test_missing_weights_never_reaches_the_model(tmp_path, write_config, monkeypatch):
    """The point of the check: nothing is loaded, so nothing can be downloaded.

    `ultralytics` is replaced by a stand-in that refuses to be used. If the
    weights check ever moves below the model load, this test says so instead of
    the machine quietly downloading a file it was told not to fetch.
    """
    trap = types.ModuleType("ultralytics")
    trap.YOLO = _refuse
    monkeypatch.setitem(sys.modules, "ultralytics", trap)

    cfg = config_pointing_at(write_config, str(tmp_path / "nowhere" / "yolo26n.pt"))

    with pytest.raises(FileNotFoundError):
        Detector(cfg)


def _refuse(*args, **kwargs):
    raise AssertionError("YOLO must not be touched when the weights file is missing")
