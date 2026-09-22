"""`bench.py`: what it agrees to measure and how it reports a comparison.

No model is loaded. `Detector` and the timing are replaced, so the numbers in
the report are the ones the test chose and the speed-up can be checked against
a value worked out by hand.
"""

import cv2
import numpy as np
import pytest

import bench

EXIT_USAGE = 2
STILLS_ONLY_MESSAGE = "bench.py measures still images: pass an image or a folder"


class StubDetector:
    def __init__(self, cfg):
        self.weights = cfg.model.weights

    def __call__(self, frame):
        return []


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "still.jpg"
    ok, encoded = cv2.imencode(".jpg", np.zeros((32, 48, 3), dtype=np.uint8))
    assert ok
    path.write_bytes(encoded.tobytes())
    return path


@pytest.mark.parametrize("source", ["clip.mp4", "camera:0", "0"])
def test_a_stream_source_is_a_usage_error(tmp_path, capsys, monkeypatch, source):
    monkeypatch.setattr(bench, "Detector", StubDetector)
    if source.endswith(".mp4"):
        (tmp_path / source).write_bytes(b"not really a video")
        source = str(tmp_path / source)

    code = bench.main(["--source", source])

    assert code == EXIT_USAGE
    assert STILLS_ONLY_MESSAGE in capsys.readouterr().err


def test_weights_takes_several_values():
    args = bench.parse_args(
        ["--source", "bus.jpg", "--weights", "models/yolo26n.pt", "models/yolo26n_openvino_model"]
    )

    assert args.weights == ["models/yolo26n.pt", "models/yolo26n_openvino_model"]


def test_each_later_model_is_reported_as_a_speedup_over_the_first(image, capsys, monkeypatch):
    # 0.200 s/frame against 0.080 s/frame: 0.200 / 0.080 = 2.5.
    seconds = {"a.pt": 0.200, "b_openvino_model": 0.080}
    monkeypatch.setattr(bench, "Detector", StubDetector)
    monkeypatch.setattr(
        bench, "measure", lambda detector, frames, runs, warmup: [seconds[detector.weights]] * runs
    )

    code = bench.main(["--source", str(image), "--runs", "2", "--weights", "a.pt", "b_openvino_model"])

    out = capsys.readouterr().out
    assert code == 0
    assert "model:   a.pt" in out
    assert "model:   b_openvino_model" in out
    assert "speedup vs first: b_openvino_model: 2.50x" in out
