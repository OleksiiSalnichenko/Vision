"""The overlay: what the user actually looks at.

Contents are ARCHITECTURE.md section 8, verbatim: a red crosshair at the centre
of the frame, a box around each object, a small green cross at each object's
centre and `dx / dy` printed inside the box. The line between the two centres
is off by default and appears only with `display.center_line: true`.

Colours, thicknesses and label layout are this module's own business (spec,
"Boundaries and seams"): they describe how the overlay looks, not what the
detector does, so they stay here as named constants instead of growing
`config.yaml`. Everything a user is expected to switch comes from `Config`.
"""

from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

from .config import Config
from .geometry import offsets
from .types import Detection

# BGR, the order OpenCV uses.
_CROSSHAIR_COLOR = (0, 0, 255)  # red, frame centre
_OBJECT_CENTRE_COLOR = (0, 255, 0)  # green, object centre
_BOX_COLOR = (0, 200, 255)  # amber; readable on both dark and light photos
_CENTRE_LINE_COLOR = (255, 255, 0)  # cyan
_TEXT_COLOR = (255, 255, 255)
_TEXT_OUTLINE_COLOR = (0, 0, 0)  # keeps text legible over a bright background

_BOX_THICKNESS = 2
_MARK_THICKNESS = 2  # crosshair and object cross: 1 px disappears on a photo
_LINE_THICKNESS = 1

_CROSSHAIR_ARM = 20  # px, arm length measured from the centre outwards
_CROSSHAIR_GAP = 5  # px, left clear around the exact centre so it stays visible
_OBJECT_CROSS_ARM = 6  # px

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE = 0.45
_FONT_THICKNESS = 1
_TEXT_OUTLINE_THICKNESS = 3
_TEXT_MARGIN = 4  # px, gap between the box edge and the text it carries


def annotate(
    image: np.ndarray, detections: Sequence[Detection], cfg: Config
) -> np.ndarray:
    """Return a copy of `image` with the overlay drawn on it.

    The input image is never modified: the same frame is also written to disk
    and handed to other consumers. An empty `detections` list is normal and
    yields the bare frame plus the crosshair.
    """
    canvas = image.copy()
    height, width = canvas.shape[:2]
    frame_centre = _frame_centre(width, height)

    if cfg.display.crosshair:
        _draw_crosshair(canvas, frame_centre)

    for detection in detections:
        _draw_detection(canvas, detection, frame_centre, cfg)

    return canvas


def _frame_centre(width: int, height: int) -> tuple[int, int]:
    """The pixel the crosshair marks, taken from `geometry.offsets` itself.

    A box covering the whole frame has its centre at the centre of the frame,
    so asking `offsets` for it returns the same point, rounded the same way,
    that the module uses as the zero of `dx`/`dy`. Repeating the arithmetic
    here with `width // 2` put the crosshair a pixel off the zero on any odd
    frame size, which is exactly the error the overlay exists to rule out.
    """
    centre, _, _, _, _ = offsets((0, 0, width, height), (width, height))
    return centre


def _draw_crosshair(canvas: np.ndarray, centre: tuple[int, int]) -> None:
    """Draw the red crosshair marking the centre of the frame."""
    x, y = centre
    cv2.line(
        canvas,
        (x - _CROSSHAIR_ARM, y),
        (x - _CROSSHAIR_GAP, y),
        _CROSSHAIR_COLOR,
        _MARK_THICKNESS,
    )
    cv2.line(
        canvas,
        (x + _CROSSHAIR_GAP, y),
        (x + _CROSSHAIR_ARM, y),
        _CROSSHAIR_COLOR,
        _MARK_THICKNESS,
    )
    cv2.line(
        canvas,
        (x, y - _CROSSHAIR_ARM),
        (x, y - _CROSSHAIR_GAP),
        _CROSSHAIR_COLOR,
        _MARK_THICKNESS,
    )
    cv2.line(
        canvas,
        (x, y + _CROSSHAIR_GAP),
        (x, y + _CROSSHAIR_ARM),
        _CROSSHAIR_COLOR,
        _MARK_THICKNESS,
    )


def _draw_detection(
    canvas: np.ndarray,
    detection: Detection,
    frame_centre: tuple[int, int],
    cfg: Config,
) -> None:
    """Draw one object: optional centre line, box, centre cross and texts."""
    x1, y1, x2, y2 = (int(round(value)) for value in detection.bbox)
    centre = (int(round(detection.center[0])), int(round(detection.center[1])))

    # The line goes first so the box and the cross stay on top of it.
    if cfg.display.center_line:
        cv2.line(
            canvas, frame_centre, centre, _CENTRE_LINE_COLOR, _LINE_THICKNESS
        )

    cv2.rectangle(canvas, (x1, y1), (x2, y2), _BOX_COLOR, _BOX_THICKNESS)
    _draw_object_centre(canvas, centre)

    if cfg.display.show_labels:
        _put_text(canvas, _label_text(detection), (x1 + _TEXT_MARGIN, y1 - _TEXT_MARGIN))

    if cfg.display.show_offsets:
        # Inside the box, as ARCHITECTURE.md section 8 requires.
        _put_text(
            canvas,
            f"{detection.dx:+d} / {detection.dy:+d}",
            (x1 + _TEXT_MARGIN, y2 - _TEXT_MARGIN),
        )


def _draw_object_centre(canvas: np.ndarray, centre: tuple[int, int]) -> None:
    """Draw the small green cross at the centre of one object."""
    x, y = centre
    cv2.line(
        canvas,
        (x - _OBJECT_CROSS_ARM, y),
        (x + _OBJECT_CROSS_ARM, y),
        _OBJECT_CENTRE_COLOR,
        _MARK_THICKNESS,
    )
    cv2.line(
        canvas,
        (x, y - _OBJECT_CROSS_ARM),
        (x, y + _OBJECT_CROSS_ARM),
        _OBJECT_CENTRE_COLOR,
        _MARK_THICKNESS,
    )


def _label_text(detection: Detection) -> str:
    """`person 0.92`, plus the colour name when `--color` filled it in."""
    text = f"{detection.cls_name} {detection.conf:.2f}"
    if detection.color:
        text = f"{text} {detection.color}"
    return text


def _put_text(canvas: np.ndarray, text: str, origin: tuple[int, int]) -> None:
    """Draw `text` with a dark outline, kept inside the frame."""
    height, width = canvas.shape[:2]
    (text_width, text_height), _ = cv2.getTextSize(
        text, _FONT, _FONT_SCALE, _FONT_THICKNESS
    )
    x = min(max(origin[0], _TEXT_MARGIN), max(width - text_width - _TEXT_MARGIN, 0))
    y = min(max(origin[1], text_height + _TEXT_MARGIN), height - _TEXT_MARGIN)

    cv2.putText(
        canvas,
        text,
        (x, y),
        _FONT,
        _FONT_SCALE,
        _TEXT_OUTLINE_COLOR,
        _TEXT_OUTLINE_THICKNESS,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        text,
        (x, y),
        _FONT,
        _FONT_SCALE,
        _TEXT_COLOR,
        _FONT_THICKNESS,
        cv2.LINE_AA,
    )
