"""`core.rules`: loading `rules.yaml` strictly, and the debouncing engine.

The engine is fed synthetic `Detection`s carrying a `track_id` and plain
numbers for stream time -- no model, no video, no clock.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from core.rules import Event, RuleEngine, RulesError, load_rules
from core.types import Detection

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID = """\
debounce:
  confirm_frames: 4
  cooldown: 2.5
zones:
  door: [0.0, 0.0, 0.3, 1.0]
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [log]
  - name: person_stays
    when: present
    seconds: 10
    do: [log, save_frame]
  - name: phone_at_door
    when: entered
    zone: door
    class: cell phone
    do: [log, {call: on_phone}]
  - name: anyone_left
    when: disappeared
    do: [{call: on_leave}]
"""


@pytest.fixture
def write_rules(tmp_path):
    def write(text: str) -> Path:
        path = tmp_path / "rules.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    return write


# --- load_rules ---------------------------------------------------------------


def test_a_valid_file_loads_with_its_own_debounce_values(write_rules):
    rule_set = load_rules(write_rules(VALID))

    assert rule_set.confirm_frames == 4
    assert rule_set.cooldown == 2.5
    assert rule_set.calls() == {"on_phone", "on_leave"}


def test_a_missing_file_is_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="rules file not found"):
        load_rules(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    ("old", "new", "named"),
    [
        ("  confirm_frames: 4\n", "", "debounce.confirm_frames"),
        ("when: appeared", "when: arrived", "rules[person_appeared].when"),
        ("    seconds: 10\n", "", "rules[person_stays].seconds"),
        ("zone: door", "zone: dor", "rules[phone_at_door].zone: unknown zone 'dor'"),
        ("[0.0, 0.0, 0.3, 1.0]", "[0.5, 0, 0.2, 1]", "zones.door"),
        ("name: person_stays", "name: person_appeared", "rules[person_appeared].name"),
        ("do: [log]", "do: []", "rules[person_appeared].do"),
        ("do: [log]", "do: [shout]", "rules[person_appeared].do"),
        ("cooldown: 2.5", "cooldown: -1", "debounce.cooldown"),
    ],
    ids=[
        "no-confirm-frames",
        "unknown-when",
        "present-without-seconds",
        "unknown-zone",
        "inverted-zone",
        "duplicate-name",
        "empty-do",
        "unknown-action",
        "negative-cooldown",
    ],
)
def test_a_broken_file_names_the_rule_and_key(write_rules, old, new, named):
    assert old in VALID
    with pytest.raises(RulesError, match=_literal(named)):
        load_rules(write_rules(VALID.replace(old, new, 1)))


def test_an_unknown_key_only_warns(write_rules, caplog):
    text = VALID.replace("    class: person\n", "    class: person\n    colour: red\n", 1)
    with caplog.at_level(logging.WARNING, logger="core.rules"):
        load_rules(write_rules(text))

    assert "rules[person_appeared].colour" in caplog.text


def test_the_shipped_rules_file_loads_and_covers_every_condition_and_action():
    rule_set = load_rules(PROJECT_ROOT / "rules.yaml")

    assert {rule.when for rule in rule_set.rules} == {
        "appeared",
        "disappeared",
        "present",
        "entered",
    }
    actions = {a if isinstance(a, str) else a[0] for r in rule_set.rules for a in r.actions}
    assert actions == {"log", "save_frame", "call"}
    assert "on_phone" in rule_set.calls()


def _literal(text: str) -> str:
    import re

    return re.escape(text)


# --- RuleEngine ---------------------------------------------------------------

STEP = 0.1  # seconds between frames: a 10 fps stream

DEBOUNCE = """\
debounce:
  confirm_frames: 3
  cooldown: 5.0
zones:
  door: [0.0, 0.0, 0.3, 1.0]
"""


def engine_for(write_rules, rules_text: str) -> RuleEngine:
    return RuleEngine(load_rules(write_rules(DEBOUNCE + "rules:\n" + rules_text)))


def det(track_id: int, cls: str = "person", at: tuple = (0.5, 0.5)) -> Detection:
    """A detection whose centre sits at `at`, given as fractions of the frame."""
    dx_pct, dy_pct = 2 * at[0] - 1, 2 * at[1] - 1
    return Detection(
        cls_id=0,
        cls_name=cls,
        conf=0.8,
        bbox=(0, 0, 10, 10),
        center=(5, 5),
        dx=0,
        dy=0,
        dx_pct=dx_pct,
        dy_pct=dy_pct,
        track_id=track_id,
    )


class Clock:
    """Feeds frames to an engine at a steady rate and keeps every event."""

    def __init__(self, engine: RuleEngine, start: float = 0.0) -> None:
        self.engine = engine
        self.frame = 0
        self.start = start
        self.events: list[Event] = []

    @property
    def time(self) -> float:
        return self.start + self.frame * STEP

    def feed(self, *detections: Detection) -> list[Event]:
        fired = self.engine.update(self.time, list(detections))
        self.events.extend(fired)
        self.frame += 1
        return fired

    def feed_many(self, count: int, *detections: Detection) -> None:
        for _ in range(count):
            self.feed(*detections)


APPEARED = "  - name: seen\n    when: appeared\n    do: [log]\n"


def test_appeared_fires_once_on_the_third_consecutive_frame(write_rules):
    clock = Clock(engine_for(write_rules, APPEARED))

    assert clock.feed(det(7)) == []
    assert clock.feed(det(7)) == []
    third = clock.feed(det(7))
    clock.feed_many(100, det(7))

    assert [(e.rule, e.when, e.detection.track_id) for e in third] == [("seen", "appeared", 7)]
    assert third[0].actions == ("log",)
    assert third[0].time == pytest.approx(2 * STEP)
    assert len(clock.events) == 1


def test_disappeared_fires_once_after_three_absent_frames(write_rules):
    clock = Clock(engine_for(write_rules, "  - name: gone\n    when: disappeared\n    do: [log]\n"))
    clock.feed_many(5, det(7, at=(0.8, 0.2)))

    assert clock.feed() == []
    assert clock.feed() == []
    third = clock.feed()
    clock.feed_many(50)

    assert [(e.rule, e.when) for e in third] == [("gone", "disappeared")]
    assert third[0].detection.dx_pct == pytest.approx(0.6)  # the last one seen
    assert len(clock.events) == 1


def test_a_track_never_confirmed_does_not_disappear(write_rules):
    clock = Clock(engine_for(write_rules, "  - name: gone\n    when: disappeared\n    do: [log]\n"))
    clock.feed_many(2, det(7))
    clock.feed_many(10)

    assert clock.events == []


def test_present_fires_once_when_the_track_has_stayed_n_seconds(write_rules):
    rules = "  - name: stays\n    when: present\n    seconds: 10\n    do: [save_frame]\n"
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(3, det(7))  # confirmed on the frame at t = 0.2
    confirmed_at = 2 * STEP

    clock.feed_many(300, det(7))  # up to t = 30.2 -- three windows long

    assert len(clock.events) == 1
    assert clock.events[0].when == "present"
    assert clock.events[0].actions == ("save_frame",)
    # frame 102 is at t = 10.2: the first with t - confirmed_at >= 10
    assert clock.events[0].time == pytest.approx(confirmed_at + 10.0)


def test_a_short_gap_neither_unconfirms_nor_restarts_present(write_rules):
    rules = APPEARED + "  - name: stays\n    when: present\n    seconds: 1\n    do: [log]\n"
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(3, det(7))  # confirmed at t = 0.2
    clock.feed_many(4, det(7))  # t = 0.3 .. 0.6
    clock.feed_many(2)  # t = 0.7, 0.8 -- gone for fewer than confirm_frames
    clock.feed_many(10, det(7))  # t = 0.9 ..

    whens = [(e.when, round(e.time, 3)) for e in clock.events]
    assert whens == [("appeared", 0.2), ("present", 1.2)]


def test_entered_fires_when_the_centre_moves_into_the_zone(write_rules):
    rules = "  - name: at_door\n    when: entered\n    zone: door\n    do: [log]\n"
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(10, det(7, at=(0.8, 0.5)))  # confirmed, outside the door

    assert clock.feed(det(7, at=(0.1, 0.5))) == []
    assert clock.feed(det(7, at=(0.1, 0.5))) == []
    third = clock.feed(det(7, at=(0.1, 0.5)))
    clock.feed_many(50, det(7, at=(0.1, 0.5)))

    assert [(e.rule, e.when) for e in third] == [("at_door", "entered")]
    assert len(clock.events) == 1


def test_a_track_first_confirmed_inside_the_zone_has_entered_it(write_rules):
    rules = "  - name: at_door\n    when: entered\n    zone: door\n    do: [log]\n"
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(10, det(7, at=(0.1, 0.5)))

    assert [(e.when, round(e.time, 3)) for e in clock.events] == [("entered", 0.2)]


def test_leaving_the_zone_briefly_is_not_a_new_entry(write_rules):
    rules = "  - name: at_door\n    when: entered\n    zone: door\n    do: [log]\n"
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(3, det(7, at=(0.1, 0.5)))  # entered at t = 0.2
    clock.feed_many(2, det(7, at=(0.8, 0.5)))  # out for two frames only
    clock.feed_many(100, det(7, at=(0.1, 0.5)))  # well past the cooldown

    assert len(clock.events) == 1


def test_leaving_the_zone_for_long_then_returning_is_a_new_entry(write_rules):
    rules = "  - name: at_door\n    when: entered\n    zone: door\n    do: [log]\n"
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(3, det(7, at=(0.1, 0.5)))  # entered at t = 0.2
    clock.feed_many(60, det(7, at=(0.8, 0.5)))  # out for 6 s
    clock.feed_many(3, det(7, at=(0.1, 0.5)))

    assert [round(e.time, 3) for e in clock.events] == [0.2, 6.5]


def test_the_cooldown_silences_a_track_that_returns_within_it(write_rules):
    clock = Clock(engine_for(write_rules, APPEARED))
    clock.feed_many(3, det(7))  # appeared at t = 0.2
    clock.feed_many(20)  # gone -- 2 s
    clock.feed_many(3, det(7))  # back and reconfirmed at t = 2.5

    assert len(clock.events) == 1


def test_the_same_track_fires_again_once_the_cooldown_is_over(write_rules):
    clock = Clock(engine_for(write_rules, APPEARED))
    clock.feed_many(3, det(7))  # appeared at t = 0.2
    clock.feed_many(60)  # gone -- 6 s
    clock.feed_many(3, det(7))  # reconfirmed at t = 6.5

    assert [round(e.time, 3) for e in clock.events] == [0.2, 6.5]


def test_a_flickering_track_does_not_flood_events(write_rules):
    # A detection oscillating 0.49 / 0.51 around the threshold reaches the
    # engine as present on one frame and absent on the next.
    rules = APPEARED + "  - name: gone\n    when: disappeared\n    do: [log]\n"
    clock = Clock(engine_for(write_rules, rules))
    for frame in range(200):
        if frame % 2 == 0:
            clock.feed(det(7))
        else:
            clock.feed()

    appeared = [e for e in clock.events if e.when == "appeared"]
    assert len(appeared) <= 1
    assert len(clock.events) <= 2


def test_a_flickering_confirmed_track_stays_confirmed(write_rules):
    rules = APPEARED + "  - name: gone\n    when: disappeared\n    do: [log]\n"
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(3, det(7))
    for frame in range(200):
        if frame % 2 == 0:
            clock.feed()
        else:
            clock.feed(det(7))

    assert [e.when for e in clock.events] == ["appeared"]


def test_two_tracks_fire_independently(write_rules):
    clock = Clock(engine_for(write_rules, APPEARED))
    clock.feed(det(1))
    clock.feed(det(1), det(2))
    first = clock.feed(det(1), det(2))
    second = clock.feed(det(1))  # track 2 missed this frame: not three in a row
    clock.feed(det(1), det(2))
    clock.feed(det(1), det(2))
    third = clock.feed(det(1), det(2))

    assert [e.detection.track_id for e in first] == [1]
    assert second == []
    assert [e.detection.track_id for e in third] == [2]


def test_the_class_filter_matches_by_name(write_rules):
    rules = (
        "  - name: phone\n    when: appeared\n    class: cell phone\n    do: [log]\n"
        "  - name: anything\n    when: appeared\n    do: [log]\n"
    )
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(3, det(1, cls="person"), det(2, cls="cell phone"))

    fired = sorted((e.rule, e.detection.track_id) for e in clock.events)
    assert fired == [("anything", 1), ("anything", 2), ("phone", 2)]


def test_events_on_one_frame_follow_the_order_of_the_file(write_rules):
    rules = (
        "  - name: first\n    when: entered\n    zone: door\n    do: [{call: on_door}]\n"
        "  - name: second\n    when: appeared\n    do: [log]\n"
    )
    clock = Clock(engine_for(write_rules, rules))
    clock.feed_many(3, det(7, at=(0.1, 0.5)))

    assert [e.rule for e in clock.events] == ["first", "second"]
    assert clock.events[0].actions == (("call", "on_door"),)


def test_confirm_frames_and_cooldown_come_from_the_file(write_rules):
    text = DEBOUNCE.replace("confirm_frames: 3", "confirm_frames: 5").replace(
        "cooldown: 5.0", "cooldown: 1.0"
    )
    clock = Clock(RuleEngine(load_rules(write_rules(text + "rules:\n" + APPEARED))))
    clock.feed_many(4, det(7))
    assert clock.events == []

    clock.feed(det(7))  # fifth consecutive frame, t = 0.4
    clock.feed_many(20)  # gone for 2 s -- longer than the 1 s cooldown
    clock.feed_many(5, det(7))  # reconfirmed at t = 2.9

    assert [round(e.time, 3) for e in clock.events] == [0.4, 2.9]


def test_detections_without_a_track_id_are_ignored(write_rules):
    clock = Clock(engine_for(write_rules, APPEARED))
    untracked = det(7)
    untracked.track_id = None
    clock.feed_many(10, untracked)

    assert clock.events == []
