"""`ui.view.to_image_point`: a click in the widget, in frame pixels.

Pure arithmetic, no `QApplication`. The expected values are worked out by hand:
a frame fitted into a widget keeps its proportions and is centred, so the
spare room is split into two equal bars, above and below or left and right.
"""

from __future__ import annotations

import os

# Before the first Qt import: never a window on the user's screen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ui.view import to_image_point


def test_same_size_maps_one_to_one():
    assert to_image_point((12, 34), (640, 480), (640, 480)) == pytest.approx((12, 34))


def test_scaled_up_without_bars():
    # 320x240 in 640x480: scale 2, no bars.
    assert to_image_point((100, 50), (640, 480), (320, 240)) == pytest.approx((50, 25))


def test_bars_above_and_below():
    # 640x480 in 640x680: scale 1, 100-pixel bars on top and bottom.
    assert to_image_point((200, 150), (640, 680), (640, 480)) == pytest.approx((200, 50))


def test_bars_left_and_right_with_scaling():
    # 200x100 in 800x200: scale 2 (the height limits), drawn 400 wide, 200-pixel bars.
    assert to_image_point((300, 60), (800, 200), (200, 100)) == pytest.approx((50, 30))


@pytest.mark.parametrize("point", [(10, 50), (199, 50), (600, 50), (799, 50)])
def test_click_in_a_side_bar_is_none(point):
    # 200x100 in 800x200: the frame spans x 200 up to (not including) 600.
    assert to_image_point(point, (800, 200), (200, 100)) is None


def test_the_last_pixel_inside_the_frame_still_counts():
    assert to_image_point((599, 199), (800, 200), (200, 100)) == pytest.approx((199.5, 99.5))


def test_click_in_the_bar_below_is_none():
    assert to_image_point((200, 600), (640, 680), (640, 480)) is None
    assert to_image_point((200, 99), (640, 680), (640, 480)) is None


def test_nothing_to_show_is_none():
    assert to_image_point((10, 10), (0, 0), (640, 480)) is None
    assert to_image_point((10, 10), (640, 480), (0, 0)) is None


def test_frame_view_click_leaves_as_frame_pixels(qtbot):
    import numpy as np
    from PySide6.QtCore import QPoint, Qt

    from ui.view import FrameView

    view = FrameView("nothing yet")
    qtbot.addWidget(view)
    view.resize(480, 300)  # an 80x60 frame fits at scale 5: 400 wide, 40-pixel side bars
    view.show_image(np.zeros((60, 80, 3), np.uint8))
    assert view.image_size() == (80, 60)

    with qtbot.assertNotEmitted(view.clicked):
        qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(20, 100))  # a bar
    with qtbot.waitSignal(view.clicked) as blocker:
        qtbot.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(240, 150))  # the middle
    assert blocker.args == pytest.approx([40.0, 30.0])
