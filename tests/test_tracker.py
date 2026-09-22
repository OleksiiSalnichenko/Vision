"""`core.tracker`: identity across frames, on synthetic boxes, with no model.

`BYTETracker` is a Kalman filter plus an assignment solver -- no weights and no
network -- so these tests drive the real one. The boxes are built by hand and
move a known amount per frame; what is asserted is only what a consumer sees:
the `track_id` on each returned `Detection`.
"""

from __future__ import annotations

import copy
from dataclasses import replace

import numpy as np
import pytest

from core.config import load_config
from core.geometry import offsets
from core.types import Detection, Frame

FRAME_SIZE = (640, 480)  # width, height
STEP = 5  # pixels each box moves per frame

# CONFIG_SCHEMA in conftest puts conf at 0.6 and conf_debug at 0.3, so a score
# of 0.9 is a confident detection and 0.4 is a near-miss.
CONFIDENT = 0.9


def detection(cls_id, cls_name, bbox, conf=CONFIDENT):
    """A `Detection` built the way `core.detector` builds one."""
    center, dx, dy, dx_pct, dy_pct = offsets(bbox, FRAME_SIZE)
    return Detection(
        cls_id=cls_id,
        cls_name=cls_name,
        conf=conf,
        bbox=bbox,
        center=center,
        dx=dx,
        dy=dy,
        dx_pct=dx_pct,
        dy_pct=dy_pct,
    )


def person(frame_no):
    """A person walking right."""
    x = 50.0 + STEP * frame_no
    return detection(0, "person", (x, 100.0, x + 60.0, 260.0))


def phone(frame_no):
    """A phone moving down, far from the person."""
    y = 60.0 + STEP * frame_no
    return detection(67, "cell phone", (400.0, y, 440.0, y + 70.0))


def bottle(frame_no):
    """A third object, placed away from the other two."""
    x = 500.0 - STEP * frame_no
    return detection(39, "bottle", (x, 330.0, x + 30.0, 420.0))


def frame(index):
    return Frame(
        image=np.zeros((FRAME_SIZE[1], FRAME_SIZE[0], 3), dtype=np.uint8),
        source="synthetic",
        index=index,
        time=index / 30.0,
    )


@pytest.fixture
def cfg(write_config):
    return load_config(write_config())


@pytest.fixture
def tracker(cfg):
    from core.tracker import Tracker

    return Tracker(cfg)


def test_moving_boxes_each_keep_one_id(tracker):
    ids = {"person": set(), "phone": set()}
    for n in range(10):
        # The detector sorts by confidence, so input order changes between
        # frames; the id has to follow the object, not its position in the list.
        dets = [person(n), phone(n)] if n % 2 else [phone(n), person(n)]
        for det in tracker.update(frame(n), dets):
            ids["person" if det.cls_name == "person" else "phone"].add(det.track_id)

    assert len(ids["person"]) == 1 and None not in ids["person"]
    assert len(ids["phone"]) == 1 and None not in ids["phone"]
    assert ids["person"] != ids["phone"]


def test_a_new_object_gets_a_new_id(tracker):
    known = set()
    bottle_ids = set()
    for n in range(10):
        dets = [person(n), phone(n)] + ([bottle(n)] if n >= 5 else [])
        tracked = tracker.update(frame(n), dets)
        known.update({tracked[0].track_id, tracked[1].track_id})
        if n >= 6:  # a track is confirmed on its second sighting
            bottle_ids.add(tracked[2].track_id)

    assert len(bottle_ids) == 1 and None not in bottle_ids
    assert bottle_ids.isdisjoint(known)


def test_an_empty_frame_in_the_middle_keeps_the_ids(tracker):
    before = [tracker.update(frame(n), [person(n), phone(n)]) for n in range(5)][-1]

    assert tracker.update(frame(5), []) == []

    after = tracker.update(frame(6), [person(6), phone(6)])
    assert [d.track_id for d in after] == [d.track_id for d in before]


def test_empty_frames_age_a_track_until_it_is_retired(write_config):
    from core.tracker import Tracker

    tracker = Tracker(load_config(write_config({"tracker.track_buffer": 2})))
    first = tracker.update(frame(0), [person(0)])[0].track_id
    for n in range(1, 5):
        tracker.update(frame(n), [])

    tracker.update(frame(5), [person(5)])
    back = tracker.update(frame(6), [person(6)])[0].track_id

    assert back is not None and back != first


def test_a_near_miss_holds_a_track_but_never_starts_one(tracker):
    first = tracker.update(frame(0), [person(0)])[0].track_id
    tracker.update(frame(1), [person(1)])
    dim = replace(person(2), conf=0.4)

    assert tracker.update(frame(2), [dim])[0].track_id == first
    assert tracker.update(frame(3), [person(3)])[0].track_id == first

    for n in range(4, 8):
        stray = replace(bottle(n), conf=0.4)
        assert tracker.update(frame(n), [person(n), stray])[1].track_id is None


def test_reset_starts_the_numbering_again(tracker):
    first = tracker.update(frame(0), [person(0), phone(0)])
    for n in range(1, 6):
        tracker.update(frame(n), [person(n), phone(n), bottle(n)])

    tracker.reset()
    again = tracker.update(frame(0), [bottle(0), person(0)])

    assert [d.track_id for d in again] == [d.track_id for d in first]


def test_inputs_are_not_mutated_and_boxes_are_the_detectors(tracker):
    for n in range(4):
        dets = [person(n), phone(n)]
        kept = copy.deepcopy(dets)
        tracked = tracker.update(frame(n), dets)

        assert dets == kept
        assert all(d.track_id is None for d in dets)
        assert [(d.bbox, d.conf, d.dx, d.dy) for d in tracked] == [
            (d.bbox, d.conf, d.dx, d.dy) for d in kept
        ]
