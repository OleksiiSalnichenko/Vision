"""`training/kaggle/train.py`: COCO JSON -> YOLO labels, by category name.

The training run itself is covered by `test_training_smoke.py`; here only the
pure conversion, on a hand-made `instances_*.json` whose category ids and order
differ from the model's class order.
"""

from __future__ import annotations

import importlib.metadata
import json
import re

import pytest

import training.kaggle.train as train_script
from conftest import PROJECT_ROOT
from training.kaggle.train import coco_labels, find_dir

# The model's order: what `data.yaml` names 0..N-1.
NAMES = ["person", "bicycle", "car", "pen", "flower"]

# COCO's own ids (1, 3, 18) and order deliberately differ from NAMES.
INSTANCES = {
    "categories": [
        {"id": 18, "name": "car"},
        {"id": 1, "name": "person"},
        {"id": 3, "name": "bicycle"},
    ],
    "images": [
        {"id": 7, "file_name": "a.jpg", "width": 100, "height": 50},
        {"id": 9, "file_name": "b.jpg", "width": 200, "height": 100},
        {"id": 11, "file_name": "empty.jpg", "width": 64, "height": 64},
    ],
    "annotations": [
        {"image_id": 7, "category_id": 18, "bbox": [10, 5, 20, 10], "iscrowd": 0},
        {"image_id": 7, "category_id": 1, "bbox": [50, 0, 50, 50], "iscrowd": 0},
        {"image_id": 9, "category_id": 3, "bbox": [0, 0, 100, 50], "iscrowd": 0},
        {"image_id": 9, "category_id": 1, "bbox": [0, 0, 10, 10], "iscrowd": 1},
    ],
}


def test_every_image_converts_by_category_name():
    labels = coco_labels(INSTANCES, NAMES, count=10, seed=0)

    # Worked by hand: a.jpg car [10,5,20,10] in 100x50 -> centre (20,10) -> 0.2 0.2, size 0.2 0.2.
    assert labels == {
        "a.jpg": ["2 0.200000 0.200000 0.200000 0.200000",
                  "0 0.750000 0.500000 0.500000 1.000000"],
        "b.jpg": ["1 0.250000 0.250000 0.500000 0.500000"],  # the crowd box is skipped
        "empty.jpg": [],  # no annotation: a negative, still an image
    }


def test_a_seeded_subset_of_the_requested_size():
    first = coco_labels(INSTANCES, NAMES, count=2, seed=3)

    assert len(first) == 2
    assert set(first) <= {"a.jpg", "b.jpg", "empty.jpg"}
    assert coco_labels(INSTANCES, NAMES, count=2, seed=3) == first


def test_a_category_the_model_does_not_know_is_refused():
    with pytest.raises(ValueError, match="car"):
        coco_labels(INSTANCES, ["person", "bicycle"], count=10, seed=0)


# --- finding the mounted datasets under /kaggle/input -------------------------

def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")


def test_find_dir_finds_a_marker_at_any_depth_up_to_four(tmp_path):
    _touch(tmp_path / "top" / "manifest.json")
    assert find_dir(tmp_path, "manifest.json") == tmp_path / "top"

    deep = tmp_path / "deep"
    _touch(deep / "a" / "b" / "c" / "d" / "manifest.json")  # four folders down
    assert find_dir(deep, "manifest.json") == deep / "a" / "b" / "c" / "d"


def test_find_dir_does_not_look_deeper_than_four(tmp_path):
    _touch(tmp_path / "a" / "b" / "c" / "d" / "e" / "manifest.json")
    assert find_dir(tmp_path, "manifest.json") is None


def test_find_dir_returns_the_folder_above_a_marker_with_a_subpath(tmp_path):
    # As the COCO dataset mounts: <owner>/<version>/coco2017/annotations/instances_train2017.json
    _touch(tmp_path / "coco" / "v1" / "coco2017" / "annotations" / "instances_train2017.json")
    assert (find_dir(tmp_path, "annotations/instances_train2017.json")
            == tmp_path / "coco" / "v1" / "coco2017")


@pytest.fixture
def on_kaggle(tmp_path, monkeypatch):
    """`main()` with no arguments, its /kaggle/input in tmp_path and pip replaced."""
    pip = []
    monkeypatch.setattr(train_script, "KAGGLE_INPUT", tmp_path / "input")
    monkeypatch.setattr(train_script, "KAGGLE_WORKING", tmp_path / "working")
    monkeypatch.setattr(train_script.subprocess, "check_call", lambda cmd, **kw: pip.append(cmd))
    (tmp_path / "input").mkdir()
    return pip


def test_on_kaggle_without_a_build_one_sentence(on_kaggle, capsys):
    assert train_script.main([]) == 2
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1
    assert "manifest.json" in err[0]
    assert on_kaggle and train_script.ULTRALYTICS_PIN in on_kaggle[0]


def test_on_kaggle_a_training_failure_keeps_its_traceback(on_kaggle, tmp_path, monkeypatch):
    """The kernel log is all the user gets: the error must arrive whole, not as one line."""
    _touch(tmp_path / "input" / "build" / "manifest.json")
    (tmp_path / "input" / "build" / "manifest.json").write_text(
        json.dumps({"mode": "rough"}), encoding="utf-8")

    def broken(*args, **kwargs):
        raise ValueError("deep inside Ultralytics")

    monkeypatch.setattr(train_script, "train", broken)
    with pytest.raises(ValueError, match="deep inside Ultralytics"):
        train_script.main([])


def test_locally_a_missing_build_is_one_sentence(tmp_path, capsys):
    assert train_script.main(["--data-root", str(tmp_path / "nope"), "--out", str(tmp_path)]) == 2
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_the_kaggle_pin_is_the_ultralytics_the_project_runs():
    from packaging.requirements import Requirement

    pinned = re.fullmatch(r"ultralytics==(\S+)", train_script.ULTRALYTICS_PIN).group(1)
    assert pinned == importlib.metadata.version("ultralytics")
    lines = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    (wanted,) = [Requirement(line) for line in lines if line.startswith("ultralytics")]
    assert wanted.specifier.contains(pinned)
