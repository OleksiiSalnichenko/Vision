"""Seam 2: core.config.load_config -- a valid file loads, a broken one fails loud."""

from pathlib import Path

import pytest

from core.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_CONFIG = """
model:
  weights: models/yolo26s.pt
  imgsz: 960
  conf: 0.6
  conf_debug: 0.3

classes:
  - person
  - bottle

display:
  show_labels: false
  show_offsets: true
  crosshair: false
  center_line: true

output:
  save_json: false
  save_image: true
  dir: results

capture:
  width: 1920
  height: 1080
"""


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_config_exposes_every_value(tmp_path):
    cfg = load_config(write_config(tmp_path, VALID_CONFIG))

    assert cfg.model.weights == "models/yolo26s.pt"
    assert cfg.model.imgsz == 960
    assert cfg.model.conf == 0.6
    assert cfg.model.conf_debug == 0.3
    assert cfg.classes == ["person", "bottle"]
    assert cfg.display.show_labels is False
    assert cfg.display.show_offsets is True
    assert cfg.display.crosshair is False
    assert cfg.display.center_line is True
    assert cfg.output.save_json is False
    assert cfg.output.save_image is True
    assert cfg.output.dir == "results"
    assert cfg.capture.width == 1920
    assert cfg.capture.height == 1080


def test_wrong_type_fails_and_the_message_names_the_key(tmp_path):
    broken = VALID_CONFIG.replace("conf: 0.6", "conf: high")

    with pytest.raises(ValueError) as failure:
        load_config(write_config(tmp_path, broken))

    assert "model.conf" in str(failure.value)


def test_value_out_of_range_fails_and_the_message_names_the_key(tmp_path):
    broken = VALID_CONFIG.replace("conf_debug: 0.3", "conf_debug: 1.4")

    with pytest.raises(ValueError) as failure:
        load_config(write_config(tmp_path, broken))

    assert "model.conf_debug" in str(failure.value)


def test_unknown_key_is_a_warning_not_a_failure(tmp_path, caplog):
    with_extra = VALID_CONFIG.replace("  crosshair: false", "  crosshair: false\n  glitter: true")

    with caplog.at_level("WARNING"):
        cfg = load_config(write_config(tmp_path, with_extra))

    assert cfg.display.crosshair is False
    assert "display.glitter" in caplog.text


# Every key of the schema in ARCHITECTURE.md section 9, plus the one this
# project adds (display.center_line), with the type the document gives it.
# Listed by hand from the document: the values are the user's to tune, the
# keys are not.
DOCUMENTED_SCHEMA = {
    "model.weights": str,
    "model.imgsz": int,
    "model.conf": float,
    "model.conf_debug": float,
    "classes": list,
    "display.show_labels": bool,
    "display.show_offsets": bool,
    "display.crosshair": bool,
    "display.center_line": bool,
    "output.save_json": bool,
    "output.save_image": bool,
    "output.dir": str,
    "capture.width": int,
    "capture.height": int,
}


def read_key(cfg, dotted_key: str):
    value = cfg
    for part in dotted_key.split("."):
        value = getattr(value, part)
    return value


@pytest.mark.parametrize("dotted_key, expected_type", DOCUMENTED_SCHEMA.items())
def test_shipped_config_carries_every_documented_key(dotted_key, expected_type):
    cfg = load_config(PROJECT_ROOT / "config.yaml")

    value = read_key(cfg, dotted_key)

    assert isinstance(value, expected_type)
    # bool is an int in Python; a flag in a size field would still be wrong.
    if expected_type is int:
        assert not isinstance(value, bool)
