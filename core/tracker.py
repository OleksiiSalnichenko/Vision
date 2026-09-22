"""Identity across frames: the same object keeps the same `track_id`.

The tracking itself is Ultralytics' `BYTETracker` -- a Kalman filter and an
assignment solver, no weights -- and this module only translates: detections go
in as an Ultralytics `Boxes`, and each tracker row comes back onto the input
detection it was built from, by index. Boxes and scores are never replaced with
the tracker's smoothed ones: `dx`/`dy` were computed by `core.geometry` from
what the detector saw, and every consumer has to agree with that.

ByteTrack's thresholds are not separate knobs. The confident band is
`model.conf` and the low band starts at `model.conf_debug`, so the near-misses
the detector already returns become ByteTrack's second association pass on
their own -- they hold a track through a dim frame without ever starting one.
Only what is ByteTrack's alone lives under `tracker:` in `config.yaml`.

No NMS and no class filter: YOLO26 removes its own duplicates, and the detector
has already applied the class whitelist.
"""

from __future__ import annotations

# First, and before anything that could reach `ultralytics`: importing the
# detector sets YOLO_OFFLINE and YOLO_AUTOINSTALL, which Ultralytics reads
# exactly once, while `ultralytics.utils` is imported. Tracking would otherwise
# be the one way into Ultralytics that switches its telemetry back on.
import core.detector  # noqa: F401  -- offline switches must precede ultralytics

from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from core.config import Config
from core.types import Detection, Frame


class Tracker:
    """Gives every detection on a stream a `track_id` that is stable over time."""

    def __init__(self, cfg: Config) -> None:
        # Lazy, like the detector's own import, and after `core.detector` above.
        from ultralytics.engine.results import Boxes  # noqa: PLC0415
        from ultralytics.trackers.byte_tracker import BYTETracker  # noqa: PLC0415

        self._boxes = Boxes
        # Every field BYTETracker reads from `args`, set explicitly rather than
        # left to Ultralytics' `bytetrack.yaml`, which this project never loads.
        args = SimpleNamespace(
            tracker_type="bytetrack",
            track_high_thresh=cfg.model.conf,
            new_track_thresh=cfg.model.conf,
            track_low_thresh=cfg.model.conf_debug,
            track_buffer=cfg.tracker.track_buffer,
            match_thresh=cfg.tracker.match_thresh,
            fuse_score=cfg.tracker.fuse_score,
        )
        self._tracker = BYTETracker(args)

    def update(self, frame: Frame, detections: list[Detection]) -> list[Detection]:
        """Return `detections` in the same order, each with its `track_id` set.

        A detection no confirmed track owns this frame -- a first sighting after
        the stream's first frame, or a near-miss that matched nothing -- comes
        back with `track_id=None`. The inputs are not modified. An empty list
        still advances the tracker, so lost tracks age and are retired on time.
        """
        height, width = frame.image.shape[:2]
        rows = np.array(
            [[*det.bbox, det.conf, det.cls_id] for det in detections],
            dtype=np.float32,
        ).reshape(-1, 6)

        tracks = self._tracker.update(self._boxes(rows, orig_shape=(height, width)), frame.image)

        ids: dict[int, int] = {}
        for track in tracks:
            # [x1, y1, x2, y2, track_id, score, cls, idx]; idx is the input row.
            ids[int(track[7])] = int(track[4])

        return [replace(det, track_id=ids.get(i)) for i, det in enumerate(detections)]

    def reset(self) -> None:
        """Forget every track and start numbering again, for a new stream."""
        self._tracker.reset()
