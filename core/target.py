"""Which one detection is the target: the one a pan-tilt head would follow.

Without a click the target is the detection nearest the frame centre, measured
with the `dx`/`dy` the detector already computed. A click locks onto a track,
and the lock outlives short gaps -- a locked target that vanishes is reported as
lost, and nothing else is picked up in its place, for as long as ByteTrack
itself would still remember the id (`tracker.track_buffer` frames).

Only tracked detections are candidates: the caller hands over the drawn list,
already at or above `conf`, so this module knows no confidence threshold.
No I/O, no image.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.config import Config
from core.types import Detection


@dataclass(frozen=True)
class TargetState:
    """The target for one frame."""

    detection: Detection | None  # the target this frame, or None
    locked: bool  # chosen by a click, not by distance
    lost: bool  # locked, but its track is absent this frame


class Targeting:
    """Keeps the click lock between frames and picks the target on each one."""

    def __init__(self, cfg: Config) -> None:
        self._track_buffer = cfg.tracker.track_buffer
        self._locked_id: int | None = None
        self._missing = 0  # consecutive frames the locked track has been absent

    def click(self, point: tuple[float, float], detections: list[Detection]) -> None:
        """Lock onto the tracked box under `point`, or release on empty space.

        `point` is `(x, y)` in source-image pixels. Where boxes nest, the
        smallest one wins -- a click on a phone held in front of a person means
        the phone.
        """
        x, y = point
        hit = [
            det
            for det in _tracked(detections)
            if det.bbox[0] <= x <= det.bbox[2] and det.bbox[1] <= y <= det.bbox[3]
        ]
        self._release()
        if hit:
            self._locked_id = min(hit, key=_area).track_id

    def _release(self) -> None:
        self._locked_id = None
        self._missing = 0

    def choose(self, detections: list[Detection], frame_size: tuple[int, int]) -> TargetState:
        """Return this frame's target.

        `frame_size` is `(width, height)`; the distance itself comes from each
        detection's `dx`/`dy`, which are already relative to the frame centre.
        """
        candidates = _tracked(detections)

        if self._locked_id is not None:
            for det in candidates:
                if det.track_id == self._locked_id:
                    self._missing = 0
                    return TargetState(det, locked=True, lost=False)

            self._missing += 1
            if self._missing <= self._track_buffer:
                return TargetState(None, locked=True, lost=True)
            # ByteTrack has retired the id by now; it cannot come back.
            self._release()

        return TargetState(_nearest(candidates), locked=False, lost=False)


def _tracked(detections: list[Detection]) -> list[Detection]:
    """Only a detection with a track can be a target: a lock needs an id."""
    return [det for det in detections if det.track_id is not None]


def _area(det: Detection) -> float:
    x1, y1, x2, y2 = det.bbox
    return (x2 - x1) * (y2 - y1)


def _nearest(candidates: list[Detection]) -> Detection | None:
    """The detection closest to the frame centre; a tie goes to higher `conf`."""
    if not candidates:
        return None
    return min(candidates, key=lambda det: (det.dx**2 + det.dy**2, -det.conf))
