"""Seam 2: core.config.load_config -- a valid file loads, a broken one fails loud."""

import pytest

from conftest import CONFIG_KEY_TYPES, PROJECT_ROOT
from core.config import load_config


def test_valid_config_exposes_every_value(write_config):
    cfg = load_config(write_config())

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
    assert cfg.capture.camera == 1
    assert cfg.capture.count == 3
    assert cfg.capture.interval == 0.5
    assert cfg.bench.runs == 4
    assert cfg.bench.warmup == 1


def test_wrong_type_fails_and_the_message_names_the_key(write_config):
    broken = write_config({"model.conf": "high"})

    with pytest.raises(ValueError) as failure:
        load_config(broken)

    assert "model.conf" in str(failure.value)


def test_value_out_of_range_fails_and_the_message_names_the_key(write_config):
    broken = write_config({"model.conf_debug": 1.4})

    with pytest.raises(ValueError) as failure:
        load_config(broken)

    assert "model.conf_debug" in str(failure.value)


def test_unknown_key_is_a_warning_not_a_failure(write_config, caplog):
    with_extra = write_config({"display.glitter": True})

    with caplog.at_level("WARNING"):
        cfg = load_config(with_extra)

    assert cfg.display.crosshair is False
    assert "display.glitter" in caplog.text


def read_key(cfg, dotted_key: str):
    value = cfg
    for part in dotted_key.split("."):
        value = getattr(value, part)
    return value


# The keys and types come from the shared schema in `conftest`, which is the
# hand-written copy of the documented one.
@pytest.mark.parametrize("dotted_key, expected_type", CONFIG_KEY_TYPES.items())
def test_shipped_config_carries_every_documented_key(dotted_key, expected_type):
    cfg = load_config(PROJECT_ROOT / "config.yaml")

    value = read_key(cfg, dotted_key)

    assert isinstance(value, expected_type)
    # bool is an int in Python; a flag in a size field would still be wrong.
    if expected_type is int:
        assert not isinstance(value, bool)
