"""Seam 2: core.config.load_config -- a valid file loads, a broken one fails loud."""

import shutil

import pytest

from conftest import CONFIG_KEY_TYPES, PROJECT_ROOT, schema_value
from core.config import ConfigError, load_config, save_values


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


@pytest.mark.parametrize("dotted_key", ["tracker.match_thresh", "display.color"])
def test_missing_key_fails_and_the_message_names_the_key(write_config, dotted_key):
    path = write_config(without=(dotted_key,))

    with pytest.raises(ValueError) as failure:
        load_config(path)

    assert dotted_key in str(failure.value)


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


# `save_values` works on a copy of the shipped file, so every comment, the
# commented-out `#weights:` line and the key order it has to keep are the real ones.
SAVED = {
    "model.conf": schema_value("model.conf"),
    "model.weights": schema_value("model.weights"),
    "classes": schema_value("classes"),
    "display.center_line": schema_value("display.center_line"),
    "display.color": schema_value("display.color"),
}


@pytest.fixture
def shipped_copy(tmp_path):
    path = tmp_path / "config.yaml"
    shutil.copyfile(PROJECT_ROOT / "config.yaml", path)
    return path


def _keyed(lines):
    """Each line paired with its `section.key` (None for comments, items, blanks)."""
    section, keyed = None, []
    for line in lines:
        stripped = line.strip()
        key = None
        if stripped and not stripped.startswith(("#", "-")) and ":" in stripped:
            name = stripped.split(":", 1)[0]
            if line.startswith((" ", "\t")):
                key = f"{section}.{name}"
            else:
                section = key = name
        keyed.append((key, line))
    return keyed


def _comment(line):
    return line[line.index(" #") :].strip() if " #" in line else None


def test_save_values_changes_only_the_values_and_keeps_the_rest(shipped_copy):
    before = shipped_copy.read_text(encoding="utf-8").splitlines()
    changed = set(SAVED)
    assert load_config(shipped_copy).model.conf != SAVED["model.conf"]

    save_values(shipped_copy, SAVED)

    after = shipped_copy.read_text(encoding="utf-8").splitlines()

    def untouched(lines):
        kept, in_classes = [], False
        for key, line in _keyed(lines):
            if key == "classes":
                in_classes = True
                continue
            if in_classes and line.lstrip().startswith("- "):
                continue
            in_classes = False
            if key in changed:
                continue
            kept.append(line)
        return kept

    # Everything except the saved values, in the same order, byte for byte:
    # the header, every comment, `#weights:` and all the other keys.
    assert untouched(after) == untouched(before)
    assert any(line.strip().startswith("#weights:") for line in after)

    # A changed line keeps its trailing comment.
    for dotted in changed - {"classes"}:
        old = [line for key, line in _keyed(before) if key == dotted]
        new = [line for key, line in _keyed(after) if key == dotted]
        assert len(new) == 1
        assert [_comment(line) for line in new] == [_comment(line) for line in old]
    head = lambda lines: next(line for line in lines if line.startswith("classes:"))  # noqa: E731
    assert _comment(head(after)) == _comment(head(before))

    # The number is written as it was given, not as 0.60000001.
    assert any(
        line.strip().startswith(f"conf: {SAVED['model.conf']} ") for line in after
    )

    cfg = load_config(shipped_copy)
    assert cfg.model.conf == SAVED["model.conf"]
    assert cfg.model.weights == SAVED["model.weights"]
    assert cfg.classes == SAVED["classes"]
    assert cfg.display.center_line == SAVED["display.center_line"]
    assert cfg.display.color == SAVED["display.color"]


@pytest.mark.parametrize(
    "values, named",
    [
        ({"model.conf": 1.5}, "model.conf"),
        ({"display.color": True, "display.glitter": True}, "display.glitter"),
        ({"model.conf": 0.4, "classes": "person"}, "classes"),
    ],
    ids=["out of range", "unknown key", "classes not a list"],
)
def test_save_values_refuses_and_leaves_the_file_as_it_was(shipped_copy, values, named):
    before = shipped_copy.read_bytes()

    with pytest.raises(ConfigError) as failure:
        save_values(shipped_copy, values)

    assert named in str(failure.value)
    assert shipped_copy.read_bytes() == before
    assert sorted(p.name for p in shipped_copy.parent.iterdir()) == ["config.yaml"]


def test_save_values_refuses_a_key_the_file_does_not_have(write_config):
    path = write_config(without=("display.color",))
    before = path.read_bytes()

    with pytest.raises(ConfigError) as failure:
        save_values(path, {"display.color": True})

    assert "display.color" in str(failure.value)
    assert path.read_bytes() == before


def test_save_values_empty_classes_keeps_the_comment_and_crlf(shipped_copy):
    crlf = shipped_copy.read_text(encoding="utf-8").replace("\n", "\r\n")
    shipped_copy.write_bytes(crlf.encode("utf-8"))
    classes_line = lambda lines: next(l for l in lines if l.startswith("classes:"))  # noqa: E731,E741
    old_comment = _comment(classes_line(crlf.split("\r\n")))

    save_values(shipped_copy, {"classes": [], "model.conf": 0.1 + 0.2})

    raw = shipped_copy.read_bytes().decode("utf-8")
    assert "\n" not in raw.replace("\r\n", "")
    lines = raw.split("\r\n")
    assert classes_line(lines).startswith("classes: []")
    assert _comment(classes_line(lines)) == old_comment
    # Slider arithmetic does not leak into the file as 0.30000000000000004.
    assert any(line.strip().startswith("conf: 0.3 ") for line in lines)
    assert load_config(shipped_copy).classes == []


def _line_of(path, leaf):
    return next(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(f"{leaf}:")
    )


@pytest.mark.parametrize("quoted", ['"out#1"', "'out#1'"], ids=["double", "single"])
def test_save_values_reads_a_hash_inside_quotes_as_part_of_the_value(write_config, quoted):
    path = write_config()
    text = path.read_text(encoding="utf-8")
    dir_line = f"  dir: {schema_value('output.dir')}\n"
    assert dir_line in text
    path.write_text(text.replace(dir_line, f"  dir: {quoted}   # where results go\n"), encoding="utf-8")

    save_values(path, {"output.dir": "elsewhere"})

    line = _line_of(path, "dir")
    assert line.split() == ["dir:", "elsewhere", "#", "where", "results", "go"]
    assert load_config(path).output.dir == "elsewhere"


def test_save_values_replaces_a_value_holding_a_hash_whole(write_config):
    path = write_config({"model.weights": "models/a#b.pt"})
    text = path.read_text(encoding="utf-8")
    old = "  weights: models/a#b.pt\n"
    assert old in text
    path.write_text(text.replace(old, "  weights: models/a#b.pt  # the model\n"), encoding="utf-8")

    save_values(path, {"model.weights": "models/c.pt"})

    assert _line_of(path, "weights").split() == ["weights:", "models/c.pt", "#", "the", "model"]
    assert load_config(path).model.weights == "models/c.pt"


def test_save_values_rewrites_classes_listed_at_column_zero(write_config):
    path = write_config()
    text = path.read_text(encoding="utf-8")
    assert "classes:\n- " in text  # YAML-legal: items not indented under the key

    save_values(path, {"classes": ["cell phone"]})

    assert load_config(path).classes == ["cell phone"]
    assert "classes:\n- cell phone\ndisplay:" in path.read_text(encoding="utf-8")


def test_save_values_refuses_classes_split_by_a_blank_line(write_config):
    path = write_config()
    text = path.read_text(encoding="utf-8")
    first = f"- {schema_value('classes')[0]}\n"
    path.write_text(text.replace(first, first + "\n"), encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ConfigError) as failure:
        save_values(path, {"classes": ["cell phone"]})

    assert "classes" in str(failure.value)
    assert path.read_bytes() == before
