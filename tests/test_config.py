"""Seam 2: core.config.load_config -- a valid file loads, a broken one fails loud."""

import pytest

from conftest import CONFIG_KEY_TYPES, PROJECT_ROOT, schema_value
from core.config import load_config


def read_key(cfg, dotted_key: str):
    value = cfg
    for part in dotted_key.split("."):
        value = getattr(value, part)
    return value


# Every value the schema in `conftest` writes has to come back from the loader
# unchanged. Those values differ from the shipped ones on purpose, so a loader
# that ignored the file it was handed could not pass.
@pytest.mark.parametrize("dotted_key", CONFIG_KEY_TYPES)
def test_valid_config_exposes_every_value(write_config, dotted_key):
    cfg = load_config(write_config())

    assert read_key(cfg, dotted_key) == schema_value(dotted_key)


def test_missing_key_fails_and_the_message_names_the_key(write_config):
    path = write_config(without=("tracker.match_thresh",))

    with pytest.raises(ValueError) as failure:
        load_config(path)

    assert "tracker.match_thresh" in str(failure.value)


@pytest.mark.parametrize(
    "dotted_key, bad_value",
    [
        ("model.conf", "high"),
        ("model.conf_debug", 1.4),
        ("tracker.match_thresh", 1.5),
        ("tracker.track_buffer", 0),
        ("tracker.track_buffer", 2.5),
        ("tracker.fuse_score", "yes"),
        ("rules.file", "  "),
    ],
)
def test_bad_value_fails_and_the_message_names_the_key(write_config, dotted_key, bad_value):
    broken = write_config({dotted_key: bad_value})

    with pytest.raises(ValueError) as failure:
        load_config(broken)

    assert dotted_key in str(failure.value)


def test_unknown_key_is_a_warning_not_a_failure(write_config, caplog):
    with_extra = write_config({"display.glitter": True})

    with caplog.at_level("WARNING"):
        cfg = load_config(with_extra)

    assert cfg.display.crosshair == schema_value("display.crosshair")
    assert "display.glitter" in caplog.text


# The keys and types come from the shared schema in `conftest`, which is the
# hand-written copy of the documented one. Only keys and types are checked: the
# values in `config.yaml` are the user's to tune.
@pytest.mark.parametrize("dotted_key, expected_type", CONFIG_KEY_TYPES.items())
def test_shipped_config_carries_every_documented_key(dotted_key, expected_type):
    cfg = load_config(PROJECT_ROOT / "config.yaml")

    value = read_key(cfg, dotted_key)

    assert isinstance(value, expected_type)
    # bool is an int in Python; a flag in a size field would still be wrong.
    if expected_type is int:
        assert not isinstance(value, bool)
