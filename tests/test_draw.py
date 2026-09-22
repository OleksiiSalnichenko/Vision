"""The overlay seam: `draw.annotate` with and without a target and a status line.

The photo overlay is pinned by a checksum rendered with the committed phase-1
module. Everything else compares two calls on the same frame: the stream look
is accepted by eye, what is asserted here is only that each new argument
changes the picture where it should.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

import numpy as np
import pytest

from core.config import load_config
from core.draw import annotate
from core.target import TargetState
from core.types import Detection

WIDTH, HEIGHT = 320, 240


@pytest.fixture
def cfg(write_config):
    return load_config(
        write_config(
            {
                "display.show_labels": True,
                "display.show_offsets": True,
                "display.crosshair": True,
                "display.center_line": False,
            }
        )
    )


def _frame() -> np.ndarray:
    # A mid-grey frame, so both a light and a dark stroke show up as a change.
    return np.full((HEIGHT, WIDTH, 3), 128, dtype=np.uint8)


def _detection(bbox=(40, 80, 120, 200), track_id=None) -> Detection:
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    return Detection(
        cls_id=0,
        cls_name="person",
        conf=0.92,
        bbox=bbox,
        center=(cx, cy),
        dx=cx - WIDTH // 2,
        dy=cy - HEIGHT // 2,
        dx_pct=(cx - WIDTH // 2) / (WIDTH / 2),
        dy_pct=(cy - HEIGHT // 2) / (HEIGHT / 2),
        track_id=track_id,
    )


# SHA-256 of the phase-1 overlay for the scene below, rendered by the committed
# phase-1 `core/draw.py` (commit 779c9d3, loaded as a separate module), not by
# the module under test. A change here means photos no longer look as they did.
PHASE_1_OVERLAY_SHA256 = "e36754630c234bf3723d4b058add8559bd72a647d89d029ff14db506817fe3fa"


def test_a_photo_overlay_is_byte_for_byte_phase_1(write_config):
    cfg = load_config(
        write_config(
            {
                "display.show_labels": True,
                "display.show_offsets": True,
                "display.crosshair": True,
                "display.center_line": True,
            }
        )
    )
    person = _detection()
    cup = replace(_detection(bbox=(200, 60, 280, 160)), cls_name="cup", conf=0.51, color="red")

    canvas = annotate(_frame(), [person, cup], cfg)

    assert hashlib.sha256(canvas.tobytes()).hexdigest() == PHASE_1_OVERLAY_SHA256


def test_the_target_box_is_drawn_differently(cfg):
    frame = _frame()
    target = _detection(track_id=7)
    other = _detection(bbox=(200, 60, 280, 160), track_id=8)

    plain = annotate(frame, [target, other], cfg)
    marked = annotate(
        frame, [target, other], cfg, target=TargetState(target, locked=False, lost=False)
    )

    x1, y1, x2, y2 = target.bbox
    # The left edge of the target box, halfway down, away from every label.
    edge = (slice(y1 + 30, y2 - 30), slice(x1 - 2, x1 + 3))
    assert not np.array_equal(plain[edge], marked[edge])
    # The other box is left exactly as it was.
    ox1, oy1, ox2, oy2 = other.bbox
    assert np.array_equal(plain[oy1 + 20 : oy2 - 20, ox1 - 2 : ox1 + 3],
                          marked[oy1 + 20 : oy2 - 20, ox1 - 2 : ox1 + 3])


def test_a_lost_target_draws_no_box(cfg):
    frame = _frame()
    detections = [_detection(track_id=8)]

    assert np.array_equal(
        annotate(frame, detections, cfg),
        annotate(frame, detections, cfg, target=TargetState(None, locked=True, lost=True)),
    )


def test_the_status_line_changes_the_top_strip_only(cfg):
    frame = _frame()

    plain = annotate(frame, [], cfg)
    with_status = annotate(frame, [], cfg, status="target #7 person  dx +120 dy -40  ->  12.3 FPS")

    assert not np.array_equal(plain[:30], with_status[:30])
    assert np.array_equal(plain[30:], with_status[30:])


def test_the_input_frame_is_not_modified(cfg):
    frame = _frame()
    target = _detection(track_id=7)

    annotate(frame, [target], cfg, target=TargetState(target, locked=True, lost=False),
             status="target: none")

    assert np.array_equal(frame, _frame())


def test_a_tracked_label_differs_from_an_untracked_one(cfg):
    frame = _frame()

    untracked = annotate(frame, [_detection(track_id=None)], cfg)
    tracked = annotate(frame, [_detection(track_id=7)], cfg)

    x1, y1 = 40, 80
    # The label strip just above the box: "#7 person 0.92" vs "person 0.92".
    assert not np.array_equal(untracked[y1 - 20 : y1, x1:], tracked[y1 - 20 : y1, x1:])
