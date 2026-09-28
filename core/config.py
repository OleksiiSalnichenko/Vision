"""Reading and validating `config.yaml`.

The file is the only place where thresholds, sizes and paths live, so this
module is deliberately strict: it knows which keys exist and refuses to guess.
"""

from __future__ import annotations

import logging
import os
import re
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
    color: bool


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
    "display.color": (bool, None),
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

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        # PyYAML's own message runs over several lines; one sentence names the file.
        raise ConfigError(f"config file is not valid YAML: {path}") from exc
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
    if _CLASSES not in data:
        raise ConfigError("missing config key: classes")
    return _checked_classes(data[_CLASSES])


def _checked_classes(raw: Any) -> list[str]:
    """The one rule for a `classes` value: a list of names; empty or null means all."""
    if raw is None:  # an empty YAML list reads as None; it means "all classes"
        return []
    if not isinstance(raw, list):
        raise ConfigError(f"config key classes must be a list, got {raw!r}")
    for index, name in enumerate(raw):
        if not isinstance(name, str):
            raise ConfigError(f"config key classes[{index}] must be text, got {name!r}")
    return list(raw)


# --- Writing values back -----------------------------------------------------
#
# The file is the user's: its comments, the commented-out alternatives and the
# key order are part of it. So it is edited line by line, never re-serialised
# through YAML, which would drop every comment.

_CLASSES = "classes"

# Floats are rounded before they are written, so a value that went through
# slider arithmetic (0.1 + 0.2) lands in the file as 0.3, not 0.30000000000000004.
_FLOAT_DIGITS = 6

# `key:` at the start of a line, followed by whitespace or nothing.
_KEY_HEAD = re.compile(r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z_]\w*):(?=[ \t]|$)")
# A block-list item, indented or at column 0 (both are legal under a key).
_ITEM_LINE = re.compile(r"^(?P<indent>[ \t]*)-(?:[ \t]|$)")
# A quote opens a quoted scalar only where a value can start.
_QUOTE_OPENERS = ": \t[{,"


@dataclass(frozen=True)
class _KeyLine:
    """One `key: value  # comment` line, as far as rewriting its value needs."""

    indent: str
    key: str
    head: str  # indent + key + ":"
    comment: str | None  # the trailing comment, `#` included
    comment_column: int


def save_values(path: str | Path, values: dict[str, Any]) -> None:
    """Write `values` into the config file at `path`, keeping everything else.

    Keys are dotted (`"model.conf"`, `"display.color"`) or `"classes"`. Only
    the value after `key:` changes: the indent and a trailing comment stay
    where they were, commented-out lines are never taken for keys, and the
    `classes` list is rewritten as a block with the indent it had. The result
    goes to a temporary file next to the original, is checked with
    `load_config`, and only then replaces it. An unknown key, a key the file
    does not have, or a value its rule refuses raises `ConfigError` naming the
    key, and the file is left as it was.
    """
    path = Path(path)
    for key, value in values.items():
        _check_saved(key, value)

    text = path.read_bytes().decode("utf-8")
    lines = text.splitlines(keepends=True)
    newline = _newline_of(lines)

    for key, value in values.items():
        if key == _CLASSES:
            lines = _replace_classes(lines, value, newline)
        else:
            lines = _replace_value(lines, key, value)

    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes("".join(lines).encode("utf-8"))
    try:
        load_config(temporary)
    except ConfigError:
        temporary.unlink()
        raise
    except Exception as error:
        temporary.unlink()
        raise ConfigError(f"config file would not load after saving: {error}") from error
    os.replace(temporary, path)


def _check_saved(key: str, value: Any) -> None:
    if key == _CLASSES:
        if value is None:
            raise ConfigError("config key classes must be a list, got None")
        _checked_classes(value)
        return
    if key not in _RULES:
        raise ConfigError(f"unknown config key: {key}")
    _checked(key, value)


def _newline_of(lines: list[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\n"


def _split_ending(line: str) -> tuple[str, str]:
    body = line.rstrip("\r\n")
    return body, line[len(body):]


def _scalar(value: Any) -> str:
    """One value in YAML syntax, quoted only when YAML needs it."""
    if isinstance(value, float):
        value = round(value, _FLOAT_DIGITS)
    dumped = yaml.safe_dump([value], allow_unicode=True, width=float("inf"))
    return dumped.strip()[2:].strip()  # "- value\n" -> "value"


def _parse_key_line(body: str) -> _KeyLine | None:
    match = _KEY_HEAD.match(body)
    if match is None:
        return None
    column = _comment_start(body, match.end())
    return _KeyLine(
        indent=match.group("indent"),
        key=match.group("key"),
        head=match.group(0),
        comment=body[column:] if column is not None else None,
        comment_column=column if column is not None else len(body),
    )


def _comment_start(body: str, start: int) -> int | None:
    """Column of the trailing comment: a `#` after whitespace, outside quotes.

    A `#` inside a value (`models/a#b`, `"out#1"`) belongs to the value, so
    rewriting the value replaces it whole and never keeps a tail as a comment.
    """
    quote = None
    previous = ":"
    index = start
    while index < len(body):
        char = body[index]
        if quote is not None:
            if quote == '"' and char == "\\":  # an escape: skip the next char
                previous = body[index + 1 : index + 2]
                index += 2
                continue
            if char == quote:
                if quote == "'" and body[index + 1 : index + 2] == "'":  # '' is a quote
                    index += 2
                    continue
                quote = None
        elif char in "\"'" and previous in _QUOTE_OPENERS:
            quote = char
        elif char == "#" and previous in " \t":
            return index
        previous = char
        index += 1
    return None


def _with_comment(head: str, line: _KeyLine) -> str:
    """`head` followed by the comment `line` carried, at the same column."""
    if line.comment is None:
        return head
    return head + " " * max(1, line.comment_column - len(head)) + line.comment


def _find_key(lines: list[str], dotted: str) -> tuple[int, _KeyLine]:
    """Index and parse of the line holding `dotted`; comments never count."""
    section = None
    wanted_section, _, wanted_key = dotted.rpartition(".")
    for index, line in enumerate(lines):
        body, _ = _split_ending(line)
        if body.lstrip().startswith("#") or not body.strip():
            continue
        parsed = _parse_key_line(body)
        if parsed is None:
            continue
        if not parsed.indent:
            section = parsed.key
            if not wanted_section and section == wanted_key:
                return index, parsed
        elif section == wanted_section and parsed.key == wanted_key:
            return index, parsed
    raise ConfigError(f"config key {dotted} not found in the file")


def _replace_value(lines: list[str], dotted: str, value: Any) -> list[str]:
    index, parsed = _find_key(lines, dotted)
    _, ending = _split_ending(lines[index])
    head = f"{parsed.head} {_scalar(value)}"
    return lines[:index] + [_with_comment(head, parsed) + ending] + lines[index + 1 :]


def _replace_classes(lines: list[str], classes: list[str], newline: str) -> list[str]:
    index, parsed = _find_key(lines, _CLASSES)
    _, ending = _split_ending(lines[index])

    end = index + 1
    indent = None
    while end < len(lines):
        item = _ITEM_LINE.match(lines[end])
        if item is None:
            break
        if indent is None:
            indent = item.group("indent")
        end += 1

    # Only a plain block of `- name` lines is rewritten. Anything else that
    # still belongs to the list -- an item after a blank or comment line, a
    # continuation line -- would survive the rewrite and change its meaning.
    for line in lines[end:]:
        body, _ = _split_ending(line)
        if not body.strip() or body.lstrip().startswith("#"):
            continue
        if body[0] in " \t" or _ITEM_LINE.match(body):
            raise ConfigError(
                "config key classes cannot be rewritten: its list has blank lines, "
                "comments or continuation lines between the items"
            )
        break

    head = parsed.head
    if not classes:
        return lines[:index] + [_with_comment(f"{head} []", parsed) + ending] + lines[end:]

    indent = "  " if indent is None else indent
    block = [_with_comment(head, parsed) + (ending or newline)]
    block += [f"{indent}- {_scalar(name)}{newline}" for name in classes]
    if not ending and end == len(lines):
        block[-1] = block[-1][: -len(newline)]
    return lines[:index] + block + lines[end:]
