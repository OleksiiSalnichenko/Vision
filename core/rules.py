"""Rules over a stream: `rules.yaml`, and debouncing of what the tracker sees.

Pure computation. This module prints nothing, writes nothing and calls no
handler -- it turns tracked detections, frame by frame, into rare `Event`s and
leaves carrying out their actions to the wiring.

Loading is as strict as `core.config`: a missing or malformed key raises
`RulesError` naming the rule and the key, an unknown key is only logged. Every
number -- frames to confirm, cooldown seconds, zone corners -- comes from the
file; none is filled in here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.types import Detection

log = logging.getLogger(__name__)

CONDITIONS = ("appeared", "disappeared", "present", "entered")
SIMPLE_ACTIONS = ("log", "save_frame")
CALL = "call"

_TOP_KEYS = {"debounce", "zones", "rules"}
_DEBOUNCE_KEYS = {"confirm_frames", "cooldown"}
_RULE_KEYS = {"name", "when", "class", "seconds", "zone", "do"}


class RulesError(ValueError):
    """A rules file that cannot be trusted. The message names the rule and key."""


@dataclass(frozen=True)
class Event:
    rule: str  # rule name from rules.yaml
    when: str  # appeared | disappeared | present | entered
    detection: Detection  # the track's latest detection
    time: float  # stream time the rule fired at
    actions: tuple  # "log", "save_frame", ("call", "name") entries


@dataclass(frozen=True)
class Rule:
    name: str
    when: str  # one of CONDITIONS
    cls: str | None  # class name to match; None means any class
    seconds: float | None  # set for "present" only
    zone: str | None  # set for "entered" only
    actions: tuple  # "log", "save_frame", ("call", "name") entries


@dataclass(frozen=True)
class RuleSet:
    confirm_frames: int  # consecutive frames before a change counts
    cooldown: float  # seconds a (rule, track) pair stays quiet after firing
    zones: dict  # name -> (x1, y1, x2, y2) as fractions of the frame
    rules: tuple  # Rule, in file order

    def calls(self) -> set[str]:
        """Every function name a `{call: ...}` action refers to."""
        return {
            action[1]
            for rule in self.rules
            for action in rule.actions
            if isinstance(action, tuple) and action[0] == CALL
        }


def load_rules(path: str | Path) -> RuleSet:
    """Load `rules.yaml` and return it as a `RuleSet`.

    Raises `FileNotFoundError` when the file is absent and `RulesError` naming
    the offending rule and key for anything malformed. An unknown key is only
    logged. Class names are not checked: the model's names are not known
    before it is loaded.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"rules file not found: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RulesError(f"rules file is not valid YAML: {path}") from exc
    if not isinstance(data, dict):
        raise RulesError(f"rules file is not a mapping: {path}")
    _warn_unknown(data, _TOP_KEYS, "")

    confirm_frames, cooldown = _debounce(data)
    zones = _zones(data)
    rules = _rules(data, zones)
    return RuleSet(confirm_frames=confirm_frames, cooldown=cooldown, zones=zones, rules=rules)


def _warn_unknown(raw: dict, known: set[str], prefix: str) -> None:
    for key in raw:
        if key not in known:
            log.warning("unknown rules key ignored: %s%s", prefix, key)


def _is_number(value: Any) -> bool:
    # bool is an int in Python; a flag in a number field is still a mistake.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _debounce(data: dict) -> tuple[int, float]:
    if "debounce" not in data:
        raise RulesError("debounce: missing required section")
    raw = data["debounce"]
    if not isinstance(raw, dict):
        raise RulesError("debounce: must be a mapping")
    _warn_unknown(raw, _DEBOUNCE_KEYS, "debounce.")

    for key in ("confirm_frames", "cooldown"):
        if key not in raw:
            raise RulesError(f"debounce.{key}: missing required key")

    frames = raw["confirm_frames"]
    if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
        raise RulesError(f"debounce.confirm_frames: must be a positive whole number, got {frames!r}")

    cooldown = raw["cooldown"]
    if not _is_number(cooldown) or cooldown < 0:
        raise RulesError(f"debounce.cooldown: must be a number not below 0, got {cooldown!r}")
    return frames, float(cooldown)


def _zones(data: dict) -> dict[str, tuple[float, float, float, float]]:
    raw = data.get("zones")
    if raw is None:  # absent, or an empty `zones:` line
        return {}
    if not isinstance(raw, dict):
        raise RulesError("zones: must be a mapping of name to [x1, y1, x2, y2]")

    zones = {}
    for name, box in raw.items():
        key = f"zones.{name}"
        if not isinstance(box, list) or len(box) != 4 or not all(_is_number(v) for v in box):
            raise RulesError(f"{key}: must be four numbers [x1, y1, x2, y2], got {box!r}")
        x1, y1, x2, y2 = (float(v) for v in box)
        if not all(0.0 <= v <= 1.0 for v in (x1, y1, x2, y2)):
            raise RulesError(f"{key}: corners must be fractions of the frame between 0 and 1, got {box!r}")
        if not (x1 < x2 and y1 < y2):
            raise RulesError(f"{key}: needs x1 < x2 and y1 < y2, got {box!r}")
        zones[str(name)] = (x1, y1, x2, y2)
    return zones


def _rules(data: dict, zones: dict) -> tuple[Rule, ...]:
    if "rules" not in data:
        raise RulesError("rules: missing required key")
    raw = data["rules"]
    if raw is None:  # an empty `rules:` line means no rules
        return ()
    if not isinstance(raw, list):
        raise RulesError("rules: must be a list")

    rules: list[Rule] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        rule = _rule(index, entry, zones)
        if rule.name in seen:
            raise RulesError(f"rules[{rule.name}].name: duplicate rule name '{rule.name}'")
        seen.add(rule.name)
        rules.append(rule)
    return tuple(rules)


def _rule(index: int, raw: Any, zones: dict) -> Rule:
    if not isinstance(raw, dict):
        raise RulesError(f"rules[{index}]: must be a mapping")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RulesError(f"rules[{index}].name: must be non-empty text, got {name!r}")
    at = f"rules[{name}]"
    _warn_unknown(raw, _RULE_KEYS, f"{at}.")

    when = raw.get("when")
    if when not in CONDITIONS:
        raise RulesError(f"{at}.when: unknown condition {when!r}, expected one of {', '.join(CONDITIONS)}")

    cls = raw.get("class")
    if cls is not None and (not isinstance(cls, str) or not cls.strip()):
        raise RulesError(f"{at}.class: must be non-empty text, got {cls!r}")

    seconds = None
    if when == "present":
        if "seconds" not in raw:
            raise RulesError(f"{at}.seconds: required for 'present'")
        seconds = raw["seconds"]
        if not _is_number(seconds) or seconds <= 0:
            raise RulesError(f"{at}.seconds: must be a positive number, got {seconds!r}")
        seconds = float(seconds)
    elif "seconds" in raw:
        log.warning("rules key ignored: %s.seconds applies to 'present' only", at)

    zone = None
    if when == "entered":
        if "zone" not in raw:
            raise RulesError(f"{at}.zone: required for 'entered'")
        zone = raw["zone"]
        if zone not in zones:
            raise RulesError(f"{at}.zone: unknown zone '{zone}'")
    elif "zone" in raw:
        log.warning("rules key ignored: %s.zone applies to 'entered' only", at)

    return Rule(name=name, when=when, cls=cls, seconds=seconds, zone=zone, actions=_actions(at, raw))


def _actions(at: str, raw: dict) -> tuple:
    if "do" not in raw:
        raise RulesError(f"{at}.do: missing required key")
    entries = raw["do"]
    if not isinstance(entries, list) or not entries:
        raise RulesError(f"{at}.do: must be a non-empty list of actions")

    actions: list = []
    for entry in entries:
        if entry in SIMPLE_ACTIONS:
            actions.append(entry)
        elif isinstance(entry, dict) and list(entry) == [CALL]:
            target = entry[CALL]
            if not isinstance(target, str) or not target.strip():
                raise RulesError(f"{at}.do: call needs a function name, got {target!r}")
            actions.append((CALL, target))
        else:
            raise RulesError(
                f"{at}.do: unknown action {entry!r}, expected log, save_frame or {{call: <name>}}"
            )
    return tuple(actions)


class _Track:
    """What the engine remembers about one track id between frames."""

    def __init__(self, zones: dict) -> None:
        self.present_run = 0  # consecutive frames seen
        self.absent_run = 0  # consecutive frames missed
        self.confirmed = False
        self.confirmed_at = 0.0  # stream time of confirmation
        self.detection: Detection | None = None  # the latest one seen
        # Debounced zone membership, and how many frames in a row the raw
        # position has disagreed with it. Unconfirmed tracks are outside all.
        self.inside = {name: False for name in zones}
        self.flip_run = {name: 0 for name in zones}
        self.present_fired: set[str] = set()  # "present" rules done this stay


class RuleEngine:
    """Turns tracked detections, frame by frame, into debounced `Event`s.

    Feed it the drawn detections of every frame of one stream, in order, with
    the stream time. Only detections carrying a `track_id` count.
    """

    def __init__(self, rule_set: RuleSet) -> None:
        self.rule_set = rule_set
        self._tracks: dict[int, _Track] = {}
        # (rule name, track id) -> stream time it last fired. Outlives the
        # track, so an id that vanishes and returns is still held quiet.
        self._last_fired: dict[tuple[str, int], float] = {}

    def update(self, time: float, detections: list[Detection]) -> list[Event]:
        """Advance one frame and return the events it fires, in file order."""
        rules = self.rule_set
        seen = {d.track_id: d for d in detections if d.track_id is not None}

        appeared: list[int] = []
        disappeared: list[tuple[int, Detection]] = []
        entered: list[tuple[int, str]] = []

        for track_id, detection in seen.items():
            track = self._tracks.get(track_id)
            if track is None:
                track = self._tracks[track_id] = _Track(rules.zones)
            track.detection = detection
            track.absent_run = 0
            track.present_run += 1
            if not track.confirmed and track.present_run >= rules.confirm_frames:
                track.confirmed = True
                track.confirmed_at = time
                appeared.append(track_id)
            entered.extend((track_id, zone) for zone in self._move(track, detection))

        for track_id in [t for t in self._tracks if t not in seen]:
            track = self._tracks[track_id]
            track.absent_run += 1
            track.present_run = 0  # a confirmed track does not depend on it any more
            if track.absent_run >= rules.confirm_frames:
                del self._tracks[track_id]
                if track.confirmed:
                    disappeared.append((track_id, track.detection))

        events: list[Event] = []
        for rule in rules.rules:
            if rule.when == "appeared":
                candidates = [(t, self._tracks[t].detection) for t in appeared]
            elif rule.when == "disappeared":
                candidates = disappeared
            elif rule.when == "entered":
                candidates = [(t, self._tracks[t].detection) for t, z in entered if z == rule.zone]
            else:
                candidates = self._present(rule, time, seen)

            for track_id, detection in candidates:
                if rule.cls is not None and detection.cls_name != rule.cls:
                    continue
                if self._cooling(rule.name, track_id, time):
                    continue
                self._last_fired[(rule.name, track_id)] = time
                if rule.when == "present":
                    self._tracks[track_id].present_fired.add(rule.name)
                events.append(Event(rule.name, rule.when, detection, time, rule.actions))

        # Forget cooldowns that are over, so a long stream does not accumulate them.
        self._last_fired = {
            key: fired for key, fired in self._last_fired.items() if time - fired < rules.cooldown
        }
        return events

    def _move(self, track: _Track, detection: Detection) -> list[str]:
        """Update zone membership; return the zones the track just entered."""
        # Frame fractions from the offsets: dx_pct is dx over half the width.
        x = 0.5 + detection.dx_pct / 2
        y = 0.5 + detection.dy_pct / 2
        just_entered = []
        for name, (x1, y1, x2, y2) in self.rule_set.zones.items():
            raw = x1 <= x <= x2 and y1 <= y <= y2
            if raw == track.inside[name]:
                track.flip_run[name] = 0
                continue
            track.flip_run[name] += 1
            if track.confirmed and track.flip_run[name] >= self.rule_set.confirm_frames:
                track.inside[name] = raw
                track.flip_run[name] = 0
                if raw:
                    just_entered.append(name)
        return just_entered

    def _present(self, rule: Rule, time: float, seen: dict) -> list[tuple[int, Detection]]:
        """Confirmed tracks in view that have stayed `rule.seconds`, once per stay."""
        return [
            (track_id, detection)
            for track_id, detection in seen.items()
            if (track := self._tracks[track_id]).confirmed
            and rule.name not in track.present_fired
            and time - track.confirmed_at >= rule.seconds
        ]

    def _cooling(self, rule: str, track_id: int, time: float) -> bool:
        last = self._last_fired.get((rule, track_id))
        return last is not None and time - last < self.rule_set.cooldown
