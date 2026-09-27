"""The frame view: the annotated frame fitted into the window, and the click on it.

`FrameView` draws the worker's canvas scaled to fit, proportions kept and
centred, with bars on the spare sides. A left click is turned back into frame
pixels by `to_image_point` -- a pure function, so the arithmetic is tested
without a display -- and leaves the widget as `clicked(x, y)`. A click in a bar
says nothing.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

# Presentation only: how small the view may get, and the colour of the bars.
_MIN_WIDTH, _MIN_HEIGHT = 320, 240
_BAR_COLOR = Qt.GlobalColor.black
_TEXT_COLOR = Qt.GlobalColor.lightGray

Size = tuple[float, float]
Point = tuple[float, float]


def fit_rect(widget_size: Size, image_size: Size) -> tuple[float, float, float, float] | None:
    """Where an image of `image_size` lands in `widget_size`: `(left, top, width, height)`.

    Scaled up or down to fit, proportions kept, centred. None when either
    size is empty.
    """
    widget_w, widget_h = widget_size
    image_w, image_h = image_size
    if widget_w <= 0 or widget_h <= 0 or image_w <= 0 or image_h <= 0:
        return None
    scale = min(widget_w / image_w, widget_h / image_h)
    width, height = image_w * scale, image_h * scale
    return (widget_w - width) / 2, (widget_h - height) / 2, width, height


def to_image_point(widget_point: Point, widget_size: Size, image_size: Size) -> Point | None:
    """`widget_point` in pixels of the fitted image, or None for a click in a bar."""
    rect = fit_rect(widget_size, image_size)
    if rect is None:
        return None
    left, top, width, height = rect
    scale = width / image_size[0]
    x = (widget_point[0] - left) / scale
    y = (widget_point[1] - top) / scale
    if not (0 <= x < image_size[0] and 0 <= y < image_size[1]):
        return None
    return x, y


def to_qimage(canvas: np.ndarray) -> QImage:
    """A BGR frame as an RGB `QImage` that owns its pixels (the array can go)."""
    rgb = np.ascontiguousarray(canvas[:, :, ::-1])
    height, width = rgb.shape[:2]
    return QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888).copy()


class FrameView(QWidget):
    """Shows one frame at a time; `clicked(x, y)` in frame pixels on a left click."""

    clicked = Signal(float, float)

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._placeholder = placeholder
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def placeholder(self) -> str:
        """The text shown while there is no frame."""
        return self._placeholder

    def has_image(self) -> bool:
        return self._image is not None

    def image_size(self) -> tuple[int, int] | None:
        """`(width, height)` of the frame on show, None before the first one."""
        if self._image is None:
            return None
        return self._image.width(), self._image.height()

    def show_image(self, canvas: np.ndarray) -> None:
        """Show a BGR frame; the view keeps its own copy."""
        self._image = to_qimage(canvas)
        self.update()

    def clear(self) -> None:
        """Back to the placeholder text."""
        self._image = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 -- Qt's name
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BAR_COLOR)
        if self._image is None:
            painter.setPen(_TEXT_COLOR)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
            return
        rect = fit_rect((self.width(), self.height()), (self._image.width(), self._image.height()))
        if rect is not None:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(QRectF(*rect), self._image)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 -- Qt's name
        if event.button() != Qt.MouseButton.LeftButton or self._image is None:
            super().mousePressEvent(event)
            return
        position = event.position()
        point = to_image_point(
            (position.x(), position.y()),
            (self.width(), self.height()),
            (self._image.width(), self._image.height()),
        )
        if point is not None:
            self.clicked.emit(point[0], point[1])
