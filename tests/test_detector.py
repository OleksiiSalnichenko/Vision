"""Seam 3: Detector.__init__ refuses to start when the weights file is absent.

This is the offline trap the brief names first: Ultralytics silently downloads
weights when it is handed a bare name, so the file must be checked before
anything in `ultralytics` is touched. These tests must never load a model and
must never reach the network.
"""

import os
import subprocess
import sys
import types

import pytest

from conftest import PROJECT_ROOT
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


MISSING_EXPORT_MESSAGE = "run scripts/export_openvino.py first"


def test_missing_openvino_folder_asks_for_the_export(tmp_path, write_config):
    cfg = config_pointing_at(write_config, str(tmp_path / "models" / "x_openvino_model"))

    with pytest.raises(FileNotFoundError) as failure:
        Detector(cfg)

    assert str(failure.value) == MISSING_EXPORT_MESSAGE


def test_openvino_folder_without_a_model_counts_as_missing(tmp_path, write_config):
    """An export that died half-way leaves the folder but no `.xml` in it."""
    folder = tmp_path / "models" / "yolo26n_openvino_model"
    folder.mkdir(parents=True)
    (folder / "metadata.yaml").write_text("imgsz: [640, 640]\n", encoding="utf-8")
    cfg = config_pointing_at(write_config, str(folder))

    with pytest.raises(FileNotFoundError) as failure:
        Detector(cfg)

    assert str(failure.value) == MISSING_EXPORT_MESSAGE


@pytest.mark.parametrize("empty", [False, True], ids=["absent", "empty"])
def test_missing_openvino_model_never_reaches_the_model(
    tmp_path, write_config, monkeypatch, empty
):
    trap = types.ModuleType("ultralytics")
    trap.YOLO = _refuse
    monkeypatch.setitem(sys.modules, "ultralytics", trap)
    folder = tmp_path / "yolo26n_openvino_model"
    if empty:
        folder.mkdir()
    cfg = config_pointing_at(write_config, str(folder))

    with pytest.raises(FileNotFoundError):
        Detector(cfg)


def test_openmp_threads_are_told_not_to_spin_before_torch_loads():
    # Intel OpenMP inside torch busy-waits 200 ms after every parallel region,
    # which on a 4-core laptop starves OpenVINO's own threads (measured: 0.18 s
    # per frame instead of 0.05). The switch only works if it is in the
    # environment before torch's OpenMP runtime starts, so check a fresh process.
    probe = (
        "import os, sys; import core.detector; "
        "print(os.environ.get('KMP_BLOCKTIME'), 'torch' in sys.modules)"
    )
    env = {key: value for key, value in os.environ.items() if key != "KMP_BLOCKTIME"}

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["0", "False"]


STUB_NAMES = {0: "person", 1: "bicycle", 39: "bottle", 67: "cell phone"}


class _StubYOLO:
    """Stands in for `ultralytics.YOLO`: knows its class names, records `predict`."""

    def __init__(self, path):
        self.names = dict(STUB_NAMES)
        self.predicted_classes = []

    def predict(self, image, **kwargs):
        self.predicted_classes.append(kwargs["classes"])
        return []


@pytest.fixture
def stub_detector(tmp_path, write_config, monkeypatch):
    """A `Detector` over a stub model, whitelisted to `person` and `bottle`."""
    stub = types.ModuleType("ultralytics")
    stub.YOLO = _StubYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", stub)
    weights = tmp_path / "stub.pt"
    weights.write_bytes(b"not a model")
    cfg = load_config(
        write_config({"model.weights": str(weights), "classes": ["person", "bottle"]})
    )
    return Detector(cfg)


def _classes_sent_to_the_model(detector):
    import numpy as np

    from core.types import Frame

    detector(Frame(image=np.zeros((8, 8, 3), dtype=np.uint8), source="stub", index=0))
    return detector._model.predicted_classes[-1]


def test_names_are_the_models_own(stub_detector):
    assert stub_detector.names == STUB_NAMES


def test_set_classes_changes_the_filter_on_the_next_frame(stub_detector):
    assert _classes_sent_to_the_model(stub_detector) == [0, 39]

    stub_detector.set_classes(["cell phone"])

    assert _classes_sent_to_the_model(stub_detector) == [67]


def test_set_classes_with_an_empty_list_means_every_class(stub_detector):
    stub_detector.set_classes([])

    assert _classes_sent_to_the_model(stub_detector) is None


def test_set_classes_refuses_an_unknown_name_and_keeps_the_filter(stub_detector):
    with pytest.raises(ValueError):
        stub_detector.set_classes(["person", "unicorn"])

    assert _classes_sent_to_the_model(stub_detector) == [0, 39]


def _refuse(*args, **kwargs):
    raise AssertionError("YOLO must not be touched when the weights file is missing")


def test_info_gives_the_size_and_leaves_unknown_what_a_stub_cannot_say(stub_detector):
    info = stub_detector.info()

    assert info.weights.endswith("stub.pt")
    assert info.size_mb == pytest.approx(len(b"not a model") / 1e6)
    assert info.params is None and info.gflops is None
