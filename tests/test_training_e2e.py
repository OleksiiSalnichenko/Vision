"""The whole phase-4 path on synthetic data, every local step for real.

A synthetic video goes through `extract_frames`; a hand-made Label Studio YOLO
export (`classes.txt` = pen, flower) of those frames goes through
`build_dataset`, with the real `models/yolo26n.pt` adding its own labels; the
build trains for one CPU epoch through `training/kaggle/train.py --smoke`; and
`evaluate` compares the result with the stock model on the build's val frames.
Every step must exit 0. Only the Kaggle upload and the Label Studio clicking
are left out: those are the user's.

One child process with the sockets trapped and an empty Ultralytics config dir
(no cached font to hide a download), as in `test_training_smoke.py`. Skipped
when `models/yolo26n.pt` is missing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import cv2
import numpy as np
import pytest

from conftest import PROJECT_ROOT, config_text
from test_training_settings import training_text

BASE_WEIGHTS = PROJECT_ROOT / "models" / "yolo26n.pt"
FRAMES = 24
STEP = 2
SIZE = (160, 120)

CHILD = r"""
import json, runpy, socket, sys, traceback
from pathlib import Path

calls = []


def trap(name, answer):
    def call(*args, **kwargs):
        where = [f"{f.filename}:{f.lineno}" for f in traceback.extract_stack()
                 if "ultralytics" in f.filename or "site-packages" not in f.filename]
        calls.append(f"{name} from {where[-3:]}")
        if isinstance(answer, Exception):
            raise answer
        return answer
    return call


socket.getaddrinfo = trap(
    "getaddrinfo", [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
)
socket.create_connection = trap("create_connection", OSError("blocked by test"))
socket.gethostbyname = trap("gethostbyname", "127.0.0.1")

project, root, base = sys.argv[1:4]
root = Path(root)
sys.path.insert(0, project)

from training import build_dataset, evaluate, extract_frames, prelabel

codes = {}
training = root / "training.yaml"
config = root / "config.yaml"

extract_frames.FRAMES_ROOT = root / "frames"
extract_frames.TRAINING_CONFIG_PATH = training
codes["extract_frames"] = extract_frames.main(["--video", str(root / "desk.mp4")])
frames = sorted((root / "frames" / "desk").glob("*.jpg"))

# What Label Studio's "YOLO" export of those frames looks like.
export = root / "export"
(export / "images").mkdir(parents=True)
(export / "labels").mkdir(parents=True)
(export / "classes.txt").write_text("pen\nflower\n", encoding="utf-8")
boxes = json.loads((root / "boxes.json").read_text(encoding="utf-8"))
for frame in frames:
    (export / "images" / frame.name).write_bytes(frame.read_bytes())
    (export / "labels" / f"{frame.stem}.txt").write_text(boxes[frame.stem], encoding="utf-8")

build_dataset.BUILD_ROOT = root / "build"
build_dataset.FRAMES_ROOT = root / "frames"
build_dataset.TRAINING_CONFIG_PATH = training
build_dataset.CONFIG_PATH = config
codes["build_dataset"] = build_dataset.main(["--export", str(export), "--name", "e2e"])

sys.argv = ["train.py", "--data-root", str(root / "build" / "e2e"), "--out", str(root / "out"),
            "--smoke"]
try:
    runpy.run_path(str(Path(project) / "training" / "kaggle" / "train.py"), run_name="__main__")
    codes["train"] = 0
except SystemExit as done:
    codes["train"] = done.code or 0

# Pre-annotating the frames with the freshly trained model, as the user does before
# drawing the rest in Label Studio.
prelabel.TRAINING_ROOT = root
prelabel.FRAMES_ROOT = root / "frames"
prelabel.TRAINING_CONFIG_PATH = training
prelabel.CONFIG_PATH = config
codes["prelabel"] = prelabel.main(["--weights", str(root / "out" / "best.pt"),
                                   "--frames", str(root / "frames" / "desk"),
                                   "--out", str(root / "tasks.json")])

evaluate.BUILD_ROOT = root / "build"
evaluate.TRAINING_CONFIG_PATH = training
evaluate.CONFIG_PATH = config
codes["evaluate"] = evaluate.main(["--weights", str(root / "out" / "best.pt"), base,
                                   "--build", "e2e", "--imgsz", "64"])
print(json.dumps({"calls": calls, "codes": codes}))
"""


def _write_video(path):
    """A pen-like bar and a flower-like disc moving on a desk; their boxes by frame stem."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, SIZE)
    assert writer.isOpened()
    width, height = SIZE
    boxes = {}
    for index in range(FRAMES):
        image = np.full((height, width, 3), 180, dtype=np.uint8)
        x = 10 + 4 * index
        cv2.rectangle(image, (x, 20), (x + 40, 28), (40, 40, 200), -1)
        lines = f"0 {(x + 20) / width:.6f} {24 / height:.6f} {40 / width:.6f} {8 / height:.6f}\n"
        if index % 4 == 0:
            cv2.circle(image, (120, 80), 15, (60, 180, 60), -1)
            lines += f"1 {120 / width:.6f} {80 / height:.6f} {30 / width:.6f} {30 / height:.6f}\n"
        if index in (6, 18):  # the scene without the objects: a negative
            image[:] = 180
            lines = ""
        writer.write(image)
        boxes[f"desk_{index:06d}"] = lines
    writer.release()
    return boxes


@pytest.mark.skipif(not BASE_WEIGHTS.is_file(), reason="models/yolo26n.pt is missing")
def test_video_to_compared_models_on_synthetic_data(tmp_path):
    boxes = _write_video(tmp_path / "desk.mp4")
    (tmp_path / "boxes.json").write_text(json.dumps(boxes), encoding="utf-8")
    (tmp_path / "training.yaml").write_text(training_text({
        "classes": ["pen", "flower"], "base_weights": "models/yolo26n.pt",
        "frames.step": STEP, "dataset.val_fraction": 0.25,
    }), encoding="utf-8")
    (tmp_path / "config.yaml").write_text(config_text({
        "model.weights": str(BASE_WEIGHTS), "bench.runs": 2, "bench.warmup": 1,
    }), encoding="utf-8")
    fonts = tmp_path / "ultralytics-config"  # Ultralytics looks for Arial.ttf here: empty
    fonts.mkdir()

    env = dict(os.environ, YOLO_CONFIG_DIR=str(fonts))
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("YOLO_OFFLINE", None)
    done = subprocess.run(
        [sys.executable, "-c", CHILD, str(PROJECT_ROOT), str(tmp_path), str(BASE_WEIGHTS)],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900,
    )
    assert done.returncode == 0, f"child failed:\n{done.stdout[-3000:]}\n{done.stderr[-3000:]}"
    result = json.loads(done.stdout.strip().splitlines()[-1])

    assert result["codes"] == {"extract_frames": 0, "build_dataset": 0, "train": 0,
                               "prelabel": 0, "evaluate": 0}, done.stderr[-3000:]
    assert result["calls"] == [], f"network reached: {result['calls']}"
    assert f"wrote {FRAMES // STEP} frames" in done.stdout
    tasks = json.loads((tmp_path / "tasks.json").read_text(encoding="utf-8"))
    assert len(tasks) == FRAMES // STEP
    rows = {line.rsplit(None, 2)[0]: line.split()[-2:]
            for line in done.stdout.splitlines() if " mAP50" in line}
    assert rows["pen mAP50"][1] == "-"  # the stock model, second column, has no pen
    assert rows["pen mAP50"][0] != "-"  # the trained one is scored on it
    assert not list(fonts.rglob("*.ttf"))
