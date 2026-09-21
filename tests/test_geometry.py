"""Seam 1: core.geometry.offsets is pure arithmetic, checked by known values.

All expected numbers below are worked out by hand from the rule in the spec:
dx = cx - width / 2, dy = cy - height / 2, dx_pct = dx / (width / 2).
"""

from core.geometry import offsets

FRAME = (640, 480)  # (width, height); frame centre is (320, 240)


def test_bbox_centred_on_frame_centre_has_zero_offsets():
    center, dx, dy, dx_pct, dy_pct = offsets((300, 220, 340, 260), FRAME)

    assert center == (320, 240)
    assert (dx, dy) == (0, 0)
    assert (dx_pct, dy_pct) == (0.0, 0.0)


def test_right_and_down_are_positive():
    # centre (630, 470): dx = 630 - 320 = 310, dy = 470 - 240 = 230
    center, dx, dy, dx_pct, dy_pct = offsets((600, 440, 660, 500), FRAME)

    assert center == (630, 470)
    assert (dx, dy) == (310, 230)
    assert dx_pct == 310 / 320
    assert dy_pct == 230 / 240


def test_left_and_up_are_negative():
    # centre (10, 10): dx = 10 - 320 = -310, dy = 10 - 240 = -230
    center, dx, dy, dx_pct, dy_pct = offsets((0, 0, 20, 20), FRAME)

    assert center == (10, 10)
    assert (dx, dy) == (-310, -230)
    assert dx_pct == -310 / 320
    assert dy_pct == -230 / 240


def test_frame_corners_reach_the_ends_of_the_percentage_range():
    _, _, _, bottom_right_x_pct, bottom_right_y_pct = offsets(
        (620, 460, 660, 500), FRAME  # centre (640, 480) — the bottom-right corner
    )
    _, _, _, top_left_x_pct, top_left_y_pct = offsets(
        (-20, -20, 20, 20), FRAME  # centre (0, 0) — the top-left corner
    )

    assert (bottom_right_x_pct, bottom_right_y_pct) == (1.0, 1.0)
    assert (top_left_x_pct, top_left_y_pct) == (-1.0, -1.0)
