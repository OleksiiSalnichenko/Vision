"""The data that crosses module boundaries. Contract only, no logic.

`Detection` is the single type every consumer reads -- drawing, JSON, console,
events and, later, servo control. Fields follow ARCHITECTURE.md section 7,
plus `Detection.track_id` and `Frame.time`, added by decisions 3 and 4 of the
phase-2 spec -- the matching change to section 7 is proposed to the user, and
nothing else is added here without that document changing first.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Detection:
    """One detected object, already expressed in source-image pixels."""

    cls_id: int  # model class index
    cls_name: str  # e.g. "person"
    conf: float  # 0..1
    bbox: tuple  # (x1, y1, x2, y2) in source-image pixels
    center: tuple  # (cx, cy)
    dx: int  # cx - frame_center_x, pixels; right is positive
    dy: int  # cy - frame_center_y, pixels; down is positive
    dx_pct: float  # dx as a fraction of half the frame width, -1..1
    dy_pct: float  # dy as a fraction of half the frame height, -1..1
    color: str | None = None  # dominant colour name, only when --color is set
    track_id: int | None = None  # set by core.tracker on streams only


@dataclass
class Frame:
    """One image on its way into the detector."""

    image: np.ndarray  # BGR, as OpenCV returns it
    source: str  # file path, or "camera:0"
    index: int  # 0 for a still image, frame number for video
    time: float = 0.0  # seconds since the stream started; 0 for stills
