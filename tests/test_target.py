"""`core.target`: which one detection the camera would be steered at.

Pure logic over `Detection` lists -- no image, no model. Offsets are built with
`core.geometry.offsets`, as the detector builds them, on a 640x480 frame whose
centre is (320, 240).
"""

from __future__ import annotations

import pytest

from core.config import load_config
from core.geometry import offsets
from core.types import Detection

FRAME_SIZE = (640, 480)


def detection(track_id, bbox, conf=0.9, cls_name="person"):
    center, dx, dy, dx_pct, dy_pct = offsets(bbox, FRAME_SIZE)
    return Detection(
        cls_id=0,
        cls_name=cls_name,
        conf=conf,
        bbox=bbox,
        center=center,
        dx=dx,
        dy=dy,
        dx_pct=dx_pct,
        dy_pct=dy_pct,
        track_id=track_id,
    )


# Centre (320, 240): dead centre.
CENTRAL = detection(1, (300.0, 220.0, 340.0, 260.0))
# Centre (470, 240): 150 px right of centre.
RIGHT = detection(2, (450.0, 200.0, 490.0, 280.0))
# Centre (120, 90): far up and left.
CORNER = detection(3, (100.0, 60.0, 140.0, 120.0))


@pytest.fixture
def cfg(write_config):
    return load_config(write_config())


@pytest.fixture
def targeting(cfg):
    from core.target import Targeting

    return Targeting(cfg)


def test_without_a_click_the_target_is_the_one_nearest_the_centre(targeting):
    state = targeting.choose([CORNER, RIGHT, CENTRAL], FRAME_SIZE)

    assert state.detection is CENTRAL
    assert state.locked is False
    assert state.lost is False


def test_a_tie_on_distance_goes_to_the_higher_confidence(targeting):
    # Centres (220, 240) and (420, 240): both exactly 100 px from the centre.
    weak = detection(4, (200.0, 220.0, 240.0, 260.0), conf=0.7)
    strong = detection(5, (400.0, 220.0, 440.0, 260.0), conf=0.8)

    assert targeting.choose([weak, strong], FRAME_SIZE).detection is strong


def test_detections_without_a_track_are_never_the_target(targeting):
    untracked = detection(None, (300.0, 220.0, 340.0, 260.0))

    assert targeting.choose([untracked, RIGHT], FRAME_SIZE).detection is RIGHT
    assert targeting.choose([untracked], FRAME_SIZE).detection is None


def test_an_empty_frame_has_no_target(targeting):
    state = targeting.choose([], FRAME_SIZE)

    assert (state.detection, state.locked, state.lost) == (None, False, False)


# A large box around RIGHT, both containing the point (470, 240).
AROUND_RIGHT = detection(6, (380.0, 120.0, 560.0, 400.0))


def test_a_click_on_nested_boxes_locks_the_smaller_one(targeting):
    targeting.click((470, 240), [AROUND_RIGHT, RIGHT, CENTRAL])
    state = targeting.choose([CENTRAL, AROUND_RIGHT, RIGHT], FRAME_SIZE)

    assert state.detection is RIGHT
    assert state.locked is True
    assert state.lost is False


def test_the_lock_follows_the_track_not_the_box(targeting):
    targeting.click((470, 240), [RIGHT, CENTRAL])
    moved = detection(2, (150.0, 300.0, 190.0, 380.0))

    assert targeting.choose([CENTRAL, moved], FRAME_SIZE).detection is moved


def test_a_click_on_empty_space_releases_the_lock(targeting):
    targeting.click((470, 240), [RIGHT, CENTRAL])
    targeting.click((20, 460), [RIGHT, CENTRAL])
    state = targeting.choose([RIGHT, CENTRAL], FRAME_SIZE)

    assert state.detection is CENTRAL
    assert state.locked is False


def test_a_lost_lock_picks_up_nothing_else(targeting):
    targeting.click((470, 240), [RIGHT, CENTRAL])
    state = targeting.choose([CENTRAL, CORNER], FRAME_SIZE)

    assert state.detection is None
    assert state.locked is True
    assert state.lost is True


def test_the_lock_is_released_after_track_buffer_frames_of_absence(targeting, cfg):
    targeting.click((470, 240), [RIGHT, CENTRAL])
    for _ in range(cfg.tracker.track_buffer):
        assert targeting.choose([CENTRAL], FRAME_SIZE).lost is True

    state = targeting.choose([CENTRAL], FRAME_SIZE)

    assert state.detection is CENTRAL
    assert (state.locked, state.lost) == (False, False)
    # Released for good: the old track coming back is not re-locked.
    assert targeting.choose([RIGHT, CENTRAL], FRAME_SIZE).detection is CENTRAL


def test_a_track_back_in_time_keeps_the_lock_and_restarts_the_count(targeting, cfg):
    targeting.click((470, 240), [RIGHT, CENTRAL])
    for _ in range(cfg.tracker.track_buffer):
        targeting.choose([CENTRAL], FRAME_SIZE)

    back = targeting.choose([CENTRAL, RIGHT], FRAME_SIZE)
    assert (back.detection, back.locked, back.lost) == (RIGHT, True, False)

    for _ in range(cfg.tracker.track_buffer):
        state = targeting.choose([CENTRAL], FRAME_SIZE)
    assert (state.detection, state.locked, state.lost) == (None, True, True)
