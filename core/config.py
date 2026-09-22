"""Reading and validating `config.yaml`.

The file is the only place where thresholds, sizes and paths live, so this
module is deliberately strict: it knows which keys exist and refuses to guess.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


class ConfigError(ValueError):
    """A config file that cannot be trusted. The message always names the key."""


@dataclass
class ModelConfig:
    weights: str
    imgsz: int
    conf: float
    conf_debug: float


@dataclass
class DisplayConfig:
    show_labels: bool
    show_offsets: bool
    crosshair: bool
    center_line: bool


@dataclass
class OutputConfig:
    save_json: bool
    save_image: bool
    dir: str


@dataclass
class CaptureConfig:
    width: int
    height: int
    camera: int
    count: int
    interval: float


@dataclass
class BenchConfig:
    runs: int
    warmup: int


@dataclass
class TrackerConfig:
    track_buffer: int
    match_thresh: float
    fuse_score: bool


@dataclass
class RulesConfig:
    file: str


@dataclass
class Config:
    model: ModelConfig
    classes: list[str]
    display: DisplayConfig
    output: OutputConfig
    capture: CaptureConfig
    bench: BenchConfig
    tracker: TrackerConfig
    rules: RulesConfig


_SECTIONS = {
    "model": ModelConfig,
    "display": DisplayConfig,
    "output": OutputConfig,
    "capture": CaptureConfig,
    "bench": BenchConfig,
    "tracker": TrackerConfig,
    "rules": RulesConfig,
}


def _positive(value: float) -> bool:
    return value > 0


def _non_negative(value: float) -> bool:
    return value >= 0


def _unit_interval(value: float) -> bool:
    return 0.0 <= value <= 1.0


def _non_empty(value: str) -> bool:
    return value.strip() != ""


# One rule per key: the type it must have, and the range it must sit in.
# These are validation bounds, not tunables -- the values themselves are in
# config.yaml and nowhere else.
_RULES: dict[str, tuple[type, Any]] = {
    "model.weights": (str, _non_empty),
    "model.imgsz": (int, _positive),
    "model.conf": (float, _unit_interval),
    "model.conf_debug": (float, _unit_interval),
    "display.show_labels": (bool, None),
    "display.show_offsets": (bool, None),
    "display.crosshair": (bool, None),
    "display.center_line": (bool, None),
    "output.save_json": (bool, None),
    "output.save_image": (bool, None),
    "output.dir": (str, _non_empty),
    "capture.width": (int, _positive),
    "capture.height": (int, _positive),
    "capture.camera": (int, _non_negative),
    "capture.count": (int, _positive),
    "capture.interval": (float, _non_negative),
    "bench.runs": (int, _positive),
    "bench.warmup": (int, _non_negative),
    "tracker.track_buffer": (int, _positive),
    "tracker.match_thresh": (float, _unit_interval),
    "tracker.fuse_score": (bool, None),
    "rules.file": (str, _non_empty),
}

_RANGE_TEXT = {
    _positive: "must be positive",
    _non_negative: "must not be negative",
    _unit_interval: "must be between 0 and 1",
    _non_empty: "must not be empty",
}


def load_config(path: str | Path) -> Config:
    """Load `config.yaml` and return it as a `Config`.

    Raises `ConfigError` naming the offending key when a key is missing, has
    the wrong type or falls outside its range. An unknown key is only logged.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"config file is not a mapping: {path}")

    for key in data:
        if key not in _SECTIONS and key != "classes":
            log.warning("unknown config key ignored: %s", key)

    sections = {name: _section(data, name, cls) for name, cls in _SECTIONS.items()}
    return Config(classes=_classes(data), **sections)


def _section(data: dict[str, Any], name: str, cls: type) -> Any:
    if name not in data:
        raise ConfigError(f"missing config section: {name}")
    raw = data[name]
    if not isinstance(raw, dict):
        raise ConfigError(f"config section must be a mapping: {name}")

    known = {field.name for field in fields(cls)}
    for key in raw:
        if key not in known:
            log.warning("unknown config key ignored: %s.%s", name, key)

    values = {}
    for field in fields(cls):
        key = f"{name}.{field.name}"
        if field.name not in raw:
            raise ConfigError(f"missing config key: {key}")
        values[field.name] = _checked(key, raw[field.name])
    return cls(**values)


def _checked(key: str, value: Any) -> Any:
    """Return `value` in its declared type, or raise `ConfigError` naming `key`."""
    expected, in_range = _RULES[key]

    if expected is bool:
        if not isinstance(value, bool):
            raise ConfigError(f"config key {key} must be true or false, got {value!r}")
    elif expected is int:
        # bool is an int in Python; a flag in a size field is still a mistake.
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"config key {key} must be a whole number, got {value!r}")
    elif expected is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"config key {key} must be a number, got {value!r}")
        value = float(value)
    elif not isinstance(value, str):
        raise ConfigError(f"config key {key} must be text, got {value!r}")

    if in_range is not None and not in_range(value):
        raise ConfigError(f"config key {key} {_RANGE_TEXT[in_range]}, got {value!r}")
    return value


def _classes(data: dict[str, Any]) -> list[str]:
    if "classes" not in data:
        raise ConfigError("missing config key: classes")
    raw = data["classes"]
    if raw is None:  # an empty YAML list reads as None; it means "all classes"
        return []
    if not isinstance(raw, list):
        raise ConfigError(f"config key classes must be a list, got {raw!r}")
    for index, name in enumerate(raw):
        if not isinstance(name, str):
            raise ConfigError(f"config key classes[{index}] must be text, got {name!r}")
    return list(raw)
