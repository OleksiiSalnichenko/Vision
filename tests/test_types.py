"""`core.types`: the defaults phase 2 added to the data contract.

Phase-1 callers build `Detection` and `Frame` without the new fields, so both
must default to what the contract in interfaces.md names: no track, time zero.
"""

import numpy as np

from core.types import Detection, Frame


def test_a_detection_built_without_a_track_id_has_none():
    det = Detection(0, "person", 0.9, (0, 0, 10, 10), (5, 5), -315, -235, -0.98, -0.98)

    assert det.track_id is None


def test_a_frame_built_without_a_time_is_at_zero():
    frame = Frame(np.zeros((4, 4, 3), dtype=np.uint8), "still.jpg", 0)

    assert frame.time == 0.0
