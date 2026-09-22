"""Shared test setup: the import path, and the one copy of the config schema.

Every test that needs a `config.yaml` builds it from `CONFIG_SCHEMA` below, so
a newly required key costs one line here instead of an edit in every test
module that writes a config file.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Every key of the schema in ARCHITECTURE.md section 9, plus the ones this
# project adds (display.center_line, capture.camera, capture.count,
# capture.interval and the whole bench section, added by task 06 for bench.py
# and scripts/grab.py; the tracker and rules sections, added by the phase-2
# spec, decision 17). Listed by hand from the documents, never read back from
# `core.config`: the keys and their types are the spec's, the values are the
# user's to tune.
#
# The values deliberately differ from the ones shipped in `config.yaml`. That
# is what makes them worth asserting -- a test reading these back can only pass
# if the loader took them from the file it was handed.
CONFIG_SCHEMA: dict[str, Any] = {
    "model": {
        "weights": "models/yolo26s.pt",
        "imgsz": 960,
        "conf": 0.6,
        "conf_debug": 0.3,
    },
    "classes": ["person", "bottle"],
    "display": {
        "show_labels": False,
        "show_offsets": True,
        "crosshair": False,
        "center_line": True,
    },
    "output": {
        "save_json": False,
        "save_image": True,
        "dir": "results",
    },
    "capture": {
        "width": 1920,
        "height": 1080,
        "camera": 1,
        "count": 3,
        "interval": 0.5,
    },
    "bench": {
        "runs": 4,
        "warmup": 1,
    },
    "tracker": {
        "track_buffer": 45,
        "match_thresh": 0.7,
        "fuse_score": False,
    },
    "rules": {
        "file": "my_rules.yaml",
    },
}


def _dotted_types(schema: dict[str, Any]) -> dict[str, type]:
    """The schema flattened to `section.key -> type`, top-level keys included."""
    flat: dict[str, type] = {}
    for name, value in schema.items():
        if isinstance(value, dict):
            for key, inner in value.items():
                flat[f"{name}.{key}"] = type(inner)
        else:
            flat[name] = type(value)
    return flat


CONFIG_KEY_TYPES = _dotted_types(CONFIG_SCHEMA)


def schema_value(dotted: str) -> Any:
    """The value `CONFIG_SCHEMA` holds under a dotted key such as `model.conf`."""
    value: Any = CONFIG_SCHEMA
    for part in dotted.split("."):
        value = value[part]
    return value


def config_text(overrides: dict[str, Any] | None = None, without: tuple[str, ...] = ()) -> str:
    """`CONFIG_SCHEMA` as YAML, with dotted keys from `overrides` applied.

    An override key that is not in the schema is added, which is how a test
    writes a config carrying a key the loader has never heard of. Dotted keys
    in `without` are removed from the data before it is serialised.
    """
    data = copy.deepcopy(CONFIG_SCHEMA)
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
def write_config(tmp_path):
    """Write a complete config into `tmp_path` and return its path.

    Takes the same dotted-key overrides and removals as `config_text`, so each
    test states only the keys it is actually about.
    """

    def write(overrides: dict[str, Any] | None = None, without: tuple[str, ...] = ()) -> Path:
        path = tmp_path / "config.yaml"
        path.write_text(config_text(overrides, without), encoding="utf-8")
        return path

    return write
