"""`training/training.yaml` and its strict loader, `training.settings.load_training`.

The schema below is listed by hand from the phase-4 spec (the paragraph that
names the `training.yaml` keys), never read back from `training.settings`. The
values deliberately differ from the shipped `training/training.yaml`, so a test
reading them back can only pass if the loader took them from the file it got.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import PROJECT_ROOT
from training.settings import TRAINING_CONFIG_PATH, TrainingConfigError, load_training

TRAINING_SCHEMA: dict[str, Any] = {
    "classes": ["stapler", "mug"],
    "base_weights": "models/yolo26s.pt",
    "frames": {"step": 15, "target_total": 600},
    "dataset": {
        "val_fraction": 0.25,
        "pseudo_conf": 0.4,
        "pseudo_iou_drop": 0.6,
        "internet_fraction": 0.3,
        "min_negative_fraction": 0.05,
        "seed": 7,
    },
    "coco": {"train_images": 1000, "val_images": 200},
    "train": {"epochs": 10, "imgsz": 960, "batch": 8},
    "rough": {"epochs": 5},
    "kaggle": {
        "username": "someone",
        "dataset_slug": "my-data",
        "kernel_slug": "my-kernel",
        "coco_dataset": "owner/coco",
    },
}


def _dotted(schema: dict[str, Any]) -> list[str]:
    keys = []
    for name, value in schema.items():
        if isinstance(value, dict):
            keys += [f"{name}.{key}" for key in value]
        else:
            keys.append(name)
    return keys


ALL_KEYS = _dotted(TRAINING_SCHEMA)


def value_of(dotted: str) -> Any:
    value: Any = TRAINING_SCHEMA
    for part in dotted.split("."):
        value = value[part]
    return value


def training_text(overrides: dict[str, Any] | None = None, without: tuple[str, ...] = ()) -> str:
    data = copy.deepcopy(TRAINING_SCHEMA)
    for dotted, value in (overrides or {}).items():
        *sections, key = dotted.split(".")
        target = data
        for section in sections:
            target = target.setdefault(section, {})
        target[key] = value
    for dotted in without:
        *sections, key = dotted.split(".")
        target = data
        for section in sections:
            target = target[section]
        del target[key]
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


@pytest.fixture
def write_training(tmp_path):
    def write(overrides: dict[str, Any] | None = None, without: tuple[str, ...] = ()) -> Path:
        path = tmp_path / "training.yaml"
        path.write_text(training_text(overrides, without), encoding="utf-8")
        return path

    return write


def test_a_complete_file_loads_with_its_values(write_training):
    cfg = load_training(write_training())
    assert cfg.classes == ["stapler", "mug"]
    assert cfg.base_weights == "models/yolo26s.pt"
    assert (cfg.frames.step, cfg.frames.target_total) == (15, 600)
    assert cfg.dataset.val_fraction == 0.25
    assert cfg.dataset.pseudo_conf == 0.4
    assert cfg.dataset.pseudo_iou_drop == 0.6
    assert cfg.dataset.internet_fraction == 0.3
    assert cfg.dataset.min_negative_fraction == 0.05
    assert cfg.dataset.seed == 7
    assert (cfg.coco.train_images, cfg.coco.val_images) == (1000, 200)
    assert (cfg.train.epochs, cfg.train.imgsz, cfg.train.batch) == (10, 960, 8)
    assert cfg.rough.epochs == 5
    assert cfg.kaggle.username == "someone"
    assert cfg.kaggle.dataset_slug == "my-data"
    assert cfg.kaggle.kernel_slug == "my-kernel"
    assert cfg.kaggle.coco_dataset == "owner/coco"


def test_the_config_is_frozen(write_training):
    cfg = load_training(write_training())
    with pytest.raises(AttributeError):
        cfg.frames.step = 1


@pytest.mark.parametrize("key", ALL_KEYS)
def test_a_missing_key_is_named(write_training, key):
    with pytest.raises(TrainingConfigError, match=rf"\b{key}\b"):
        load_training(write_training(without=(key,)))


@pytest.mark.parametrize("key", ALL_KEYS)
def test_a_value_of_the_wrong_type_is_named(write_training, key):
    wrong = 5 if isinstance(value_of(key), str) else "many"
    with pytest.raises(TrainingConfigError, match=rf"\b{key}\b"):
        load_training(write_training({key: wrong}))


# Every key with a range, and one value just outside it.
OUT_OF_RANGE = {
    "classes": [],
    "base_weights": "  ",
    "frames.step": 0,
    "frames.target_total": 0,
    "dataset.val_fraction": 1.0,
    "dataset.pseudo_conf": 1.5,
    "dataset.pseudo_iou_drop": -0.1,
    "dataset.internet_fraction": 1.0,
    "dataset.min_negative_fraction": 1.2,
    "dataset.seed": -1,
    "coco.train_images": -1,
    "coco.val_images": -1,
    "train.epochs": 0,
    "train.imgsz": 0,
    "train.batch": 0,
    "rough.epochs": 0,
    "kaggle.dataset_slug": "",
    "kaggle.kernel_slug": "",
    "kaggle.coco_dataset": "",
}


@pytest.mark.parametrize("key, value", sorted(OUT_OF_RANGE.items()))
def test_a_value_out_of_range_is_named(write_training, key, value):
    with pytest.raises(TrainingConfigError, match=rf"\b{key}\b"):
        load_training(write_training({key: value}))


def test_every_key_but_the_username_has_a_range_rule():
    assert set(OUT_OF_RANGE) == set(ALL_KEYS) - {"kaggle.username"}


def test_an_empty_username_is_the_placeholder_and_loads(write_training):
    assert load_training(write_training({"kaggle.username": ""})).kaggle.username == ""


@pytest.mark.parametrize("classes", [["pen", "pen"], ["pen", ""], ["pen", 3]])
def test_classes_must_be_distinct_names(write_training, classes):
    with pytest.raises(TrainingConfigError, match=r"\bclasses\b"):
        load_training(write_training({"classes": classes}))


def test_val_fraction_zero_is_refused(write_training):
    with pytest.raises(TrainingConfigError, match=r"dataset\.val_fraction"):
        load_training(write_training({"dataset.val_fraction": 0.0}))


def test_a_whole_number_is_accepted_for_a_fraction(write_training):
    cfg = load_training(write_training({"dataset.min_negative_fraction": 0}))
    assert cfg.dataset.min_negative_fraction == 0.0


def test_a_flag_is_not_a_number(write_training):
    with pytest.raises(TrainingConfigError, match=r"train\.epochs"):
        load_training(write_training({"train.epochs": True}))


def test_unknown_keys_only_warn(write_training, caplog):
    path = write_training({"extra": 1, "train.lr": 0.01})
    with caplog.at_level(logging.WARNING):
        cfg = load_training(path)
    assert cfg.train.epochs == 10
    assert "extra" in caplog.text
    assert "train.lr" in caplog.text


def test_a_missing_section_is_named(write_training):
    with pytest.raises(TrainingConfigError, match=r"\bcoco\b"):
        load_training(write_training(without=("coco",)))


def test_a_file_that_is_not_yaml_is_one_sentence(tmp_path):
    path = tmp_path / "training.yaml"
    path.write_text("classes: [pen\n", encoding="utf-8")
    with pytest.raises(TrainingConfigError, match="not valid YAML"):
        load_training(path)


def test_a_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="training config file not found"):
        load_training(tmp_path / "nope.yaml")


def test_the_shipped_file_is_the_default_path_and_loads():
    assert TRAINING_CONFIG_PATH == PROJECT_ROOT / "training" / "training.yaml"
    cfg = load_training(TRAINING_CONFIG_PATH)
    assert cfg.classes == ["pen", "flower"]
    assert cfg.kaggle.username == ""


def test_the_shipped_file_carries_every_key_and_no_other():
    data = yaml.safe_load(TRAINING_CONFIG_PATH.read_text(encoding="utf-8"))
    assert sorted(_dotted(data)) == sorted(ALL_KEYS)


def test_the_shipped_file_comments_every_key():
    lines = TRAINING_CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    uncommented = []
    for number, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            continue
        if stripped.endswith(":") and not line.startswith(" "):
            continue  # a section header; its keys carry the comments
        previous = lines[number - 1].strip() if number else ""
        if "#" not in line and not previous.startswith("#"):
            uncommented.append(stripped)
    assert uncommented == []


def test_the_username_placeholder_says_what_to_fill_in():
    text = TRAINING_CONFIG_PATH.read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if line.strip().startswith("username:"))
    assert 'username: ""' in line
    assert "your Kaggle login" in line
