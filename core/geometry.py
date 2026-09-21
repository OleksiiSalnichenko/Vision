"""Offset arithmetic: where an object sits relative to the centre of the frame.

Pure functions only. Coordinates are pixels of the source image -- Ultralytics
already undoes its own letterbox transform before returning boxes.
"""

from __future__ import annotations

Bbox = tuple[float, float, float, float]
FrameSize = tuple[int, int]


def offsets(
    bbox: Bbox, frame_size: FrameSize
) -> tuple[tuple[int, int], int, int, float, float]:
    """Return (center, dx, dy, dx_pct, dy_pct) for one bounding box.

    `bbox` is (x1, y1, x2, y2) and `frame_size` is (width, height), both in
    pixels of the source image. `dx` is `cx - width / 2` and `dy` is
    `cy - height / 2`, so right and down are positive. The percentages are the
    same offsets divided by half the frame, which puts them in -1..1 for any
    box centre that lies inside the frame.
    """
    width, height = frame_size
    if width <= 0 or height <= 0:
        raise ValueError(f"frame_size must be positive, got {frame_size!r}")

    x1, y1, x2, y2 = bbox
    center = (int(round((x1 + x2) / 2)), int(round((y1 + y2) / 2)))

    half_width = width / 2
    half_height = height / 2
    dx = int(round(center[0] - half_width))
    dy = int(round(center[1] - half_height))

    return center, dx, dy, dx / half_width, dy / half_height
