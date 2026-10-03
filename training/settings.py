"""Reading and validating `training/training.yaml`.

Every number phase 4 lets the user turn lives in that file, and this loader is
as strict as `core/config.py`: every key is required, a missing or malformed one
raises naming the key, an unknown one is only logged. It imports nothing from
`core/`, because the training script on Kaggle reads the same file without it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

TRAINING_CONFIG_PATH = Path(__file__).resolve().parent / "training.yaml"


class TrainingConfigError(ValueError):
    """A training config that cannot be trusted. The message always names the key."""


@dataclass(frozen=True)
class FramesConfig:
    step: int
    target_total: int


@dataclass(frozen=True)
class DatasetConfig:
    val_fraction: float
    pseudo_conf: float
    pseudo_iou_drop: float
    internet_fraction: float
    min_negative_fraction: float
    seed: int


@dataclass(frozen=True)
class CocoConfig:
    train_images: int
    val_images: int


@dataclass(frozen=True)
class TrainConfig:
    epochs: int
    imgsz: int
    batch: int


@dataclass(frozen=True)
class RoughConfig:
    epochs: int


@dataclass(frozen=True)
class KaggleConfig:
    username: str
    dataset_slug: str
    kernel_slug: str
    coco_dataset: str


@dataclass(frozen=True)
class TrainingConfig:
    classes: list[str]
    base_weights: str
    frames: FramesConfig
    dataset: DatasetConfig
    coco: CocoConfig
    train: TrainConfig
    rough: RoughConfig
    kaggle: KaggleConfig


_SECTIONS = {
    "frames": FramesConfig,
    "dataset": DatasetConfig,
    "coco": CocoConfig,
    "train": TrainConfig,
    "rough": RoughConfig,
    "kaggle": KaggleConfig,
}
_TOP_KEYS = ("classes", "base_weights")


def _positive(value: float) -> bool:
    return value > 0


def _non_negative(value: float) -> bool:
    return value >= 0


def _unit_interval(value: float) -> bool:
    return 0.0 <= value <= 1.0


def _open_fraction(value: float) -> bool:
    return 0.0 < value < 1.0


def _below_one(value: float) -> bool:
    return 0.0 <= value < 1.0


def _non_empty(value: str) -> bool:
    return value.strip() != ""


# One rule per key: its type and the range it must sit in. Validation bounds,
# not tunables -- the values are in training.yaml and nowhere else.
# `kaggle.username` may be empty: that is the placeholder until the user fills it in.
_RULES: dict[str, tuple[type, Any]] = {
    "base_weights": (str, _non_empty),
    "frames.step": (int, _positive),
    "frames.target_total": (int, _positive),
    "dataset.val_fraction": (float, _open_fraction),
    "dataset.pseudo_conf": (float, _unit_interval),
    "dataset.pseudo_iou_drop": (float, _unit_interval),
    "dataset.internet_fraction": (float, _below_one),
    "dataset.min_negative_fraction": (float, _unit_interval),
    "dataset.seed": (int, _non_negative),
    "coco.train_images": (int, _non_negative),
    "coco.val_images": (int, _non_negative),
    "train.epochs": (int, _positive),
    "train.imgsz": (int, _positive),
    "train.batch": (int, _positive),
    "rough.epochs": (int, _positive),
    "kaggle.username": (str, None),
    "kaggle.dataset_slug": (str, _non_empty),
    "kaggle.kernel_slug": (str, _non_empty),
    "kaggle.coco_dataset": (str, _non_empty),
}

_RANGE_TEXT = {
    _positive: "must be positive",
    _non_negative: "must not be negative",
    _unit_interval: "must be between 0 and 1",
    _open_fraction: "must be above 0 and below 1",
    _below_one: "must be at least 0 and below 1",
    _non_empty: "must not be empty",
}


def load_training(path: str | Path = TRAINING_CONFIG_PATH) -> TrainingConfig:
    """Load `training.yaml` and return it as a frozen `TrainingConfig`.

    Raises `TrainingConfigError` naming the key when one is missing, has the
    wrong type or falls outside its range; `FileNotFoundError` when the file
    is not there. An unknown key is only logged.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"training config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TrainingConfigError(f"training config file is not valid YAML: {path}") from exc
    if not isinstance(data, dict):
        raise TrainingConfigError(f"training config file is not a mapping: {path}")

    for key in data:
        if key not in _SECTIONS and key not in _TOP_KEYS:
            log.warning("unknown training config key ignored: %s", key)

    for key in _TOP_KEYS:
        if key not in data:
            raise TrainingConfigError(f"missing training config key: {key}")
    sections = {name: _section(data, name, cls) for name, cls in _SECTIONS.items()}
    return TrainingConfig(
        classes=_classes(data["classes"]),
        base_weights=_checked("base_weights", data["base_weights"]),
        **sections,
    )


def _section(data: dict[str, Any], name: str, cls: type) -> Any:
    if name not in data:
        raise TrainingConfigError(f"missing training config section: {name}")
    raw = data[name]
    if not isinstance(raw, dict):
        raise TrainingConfigError(f"training config section must be a mapping: {name}")

    known = {field.name for field in fields(cls)}
    for key in raw:
        if key not in known:
            log.warning("unknown training config key ignored: %s.%s", name, key)

    values = {}
    for field in fields(cls):
        key = f"{name}.{field.name}"
        if field.name not in raw:
            raise TrainingConfigError(f"missing training config key: {key}")
        values[field.name] = _checked(key, raw[field.name])
    return cls(**values)


def _checked(key: str, value: Any) -> Any:
    """Return `value` in its declared type, or raise naming `key`."""
    expected, in_range = _RULES[key]
    if expected is int:
        # bool is an int in Python; a flag in a count is still a mistake.
        if isinstance(value, bool) or not isinstance(value, int):
            raise TrainingConfigError(
                f"training config key {key} must be a whole number, got {value!r}")
    elif expected is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TrainingConfigError(f"training config key {key} must be a number, got {value!r}")
        value = float(value)
    elif not isinstance(value, str):
        raise TrainingConfigError(f"training config key {key} must be text, got {value!r}")

    if in_range is not None and not in_range(value):
        raise TrainingConfigError(
            f"training config key {key} {_RANGE_TEXT[in_range]}, got {value!r}")
    return value


def _classes(raw: Any) -> list[str]:
    """The new class names: a non-empty list of distinct, non-blank names."""
    if not isinstance(raw, list) or not raw:
        raise TrainingConfigError(
            f"training config key classes must be a non-empty list, got {raw!r}")
    for index, name in enumerate(raw):
        if not isinstance(name, str) or not name.strip():
            raise TrainingConfigError(
                f"training config key classes[{index}] must be a name, got {name!r}")
    duplicates = sorted({name for name in raw if raw.count(name) > 1})
    if duplicates:
        raise TrainingConfigError(
            f"training config key classes lists a name twice: {', '.join(duplicates)}")
    return list(raw)
