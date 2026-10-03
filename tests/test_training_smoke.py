"""The whole training path, for real, before anything is uploaded to Kaggle.

A synthetic build folder (the shared format in the phase-4 interfaces: a few
frames with drawn boxes, 82 names, `training.yaml`, base weights, manifest) goes
through `training/kaggle/train.py --smoke`: one CPU epoch at a tiny image size.
The result must carry 82 names with `pen`/`flower` at 80/81, export to OpenVINO
with `scripts/export_openvino.py`, and load in `core.detector.Detector`, whose
class filter accepts `pen`.

All of it runs in one child process with the sockets trapped, as in
`test_offline.py`: Ultralytics mutes itself under pytest, and the training
script has to stay offline on its own. Skipped when `models/yolo26n.pt` is
missing (it comes from `scripts/fetch_models.py`).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np
import pytest
import yaml

from conftest import PROJECT_ROOT
from test_training_settings import training_text

BASE_WEIGHTS = PROJECT_ROOT / "models" / "yolo26n.pt"
NAMES = [f"base{i}" for i in range(80)] + ["pen", "flower"]

CHILD = r"""
import dataclasses, json, runpy, socket, sys, traceback
from pathlib import Path

calls = []


def trap(name, answer):
    def call(*args, **kwargs):
        # Who asked: the last frames are enough to find the culprit.
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

project, build, out = sys.argv[1:4]
sys.path.insert(0, project)

sys.argv = ["train.py", "--data-root", build, "--out", out, "--smoke"]
try:
    runpy.run_path(str(Path(project) / "training" / "kaggle" / "train.py"), run_name="__main__")
except SystemExit as done:
    assert not done.code, f"train.py exited {done.code}"

from ultralytics import YOLO

best = Path(out) / "best.pt"
trained_names = YOLO(str(best)).names

import core.detector
from core.config import load_config
from detect import CONFIG_PATH
from scripts.export_openvino import main as export_main

assert export_main(["--weights", str(best)]) == 0
folder = best.with_name(best.stem + core.detector.OPENVINO_SUFFIX)

cfg = load_config(CONFIG_PATH)
# No whitelist: the user's config.yaml names classes the placeholder base names lack.
cfg = dataclasses.replace(
    cfg, classes=[], model=dataclasses.replace(cfg.model, weights=str(folder)))
detector = core.detector.Detector(cfg)
detector.set_classes(["pen"])

print(json.dumps({
    "calls": calls,
    "trained": [trained_names[i] for i in sorted(trained_names)],
    "detector": [detector.names[i] for i in sorted(detector.names)],
    "folder": str(folder),
}))
"""


def _write_build(root):
    """The shared build format, with four 64x64 frames: two train, two val."""
    boxes = {  # stem -> (class, x0, y0, x1, y1) in pixels
        "train_a": (80, 8, 8, 40, 24), "train_b": (81, 20, 20, 56, 56),
        "val_a": (80, 10, 30, 50, 44), "val_b": None,
    }
    for stem, box in boxes.items():
        split = stem.split("_")[0]
        image = np.full((64, 64, 3), 200, dtype=np.uint8)
        lines = ""
        if box is not None:
            cls, x0, y0, x1, y1 = box
            cv2.rectangle(image, (x0, y0), (x1, y1), (0, 0, 255), -1)
            lines = (f"{cls} {(x0 + x1) / 128:.6f} {(y0 + y1) / 128:.6f} "
                     f"{(x1 - x0) / 64:.6f} {(y1 - y0) / 64:.6f}\n")
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        (root / "images" / split / f"{stem}.jpg").write_bytes(encoded.tobytes())
        (root / "labels" / split / f"{stem}.txt").write_text(lines, encoding="utf-8")

    (root / "data.yaml").write_text(yaml.safe_dump({
        "path": ".", "train": "images/train", "val": "images/val",
        "names": dict(enumerate(NAMES)),
    }, sort_keys=False), encoding="utf-8")
    (root / "training.yaml").write_text(
        training_text({"base_weights": "models/yolo26n.pt", "classes": ["pen", "flower"]}),
        encoding="utf-8")
    shutil.copy2(BASE_WEIGHTS, root / BASE_WEIGHTS.name)
    (root / "manifest.json").write_text(json.dumps({
        "name": "smoke", "mode": "full", "classes": NAMES,
        "counts": {"train": {"pen": 1, "flower": 1}, "val": {"pen": 1}},
        "images": {"train": 2, "val": 2}, "negatives": 1, "sources": {"own": 4, "extra": 0},
    }), encoding="utf-8")


@pytest.mark.skipif(not BASE_WEIGHTS.is_file(), reason="models/yolo26n.pt is missing")
def test_smoke_training_gives_an_82_class_model_that_exports_and_loads(tmp_path):
    build = tmp_path / "build"
    out = tmp_path / "out"
    _write_build(build)

    env = dict(os.environ)
    # The script has to switch Ultralytics offline itself, as on a fresh machine.
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("YOLO_OFFLINE", None)
    done = subprocess.run(
        [sys.executable, "-c", CHILD, str(PROJECT_ROOT), str(build), str(out)],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
    )
    assert done.returncode == 0, f"child failed:\n{done.stdout[-3000:]}\n{done.stderr[-3000:]}"
    result = json.loads(done.stdout.strip().splitlines()[-1])

    assert result["calls"] == [], f"network reached during training: {result['calls']}"
    assert len(result["trained"]) == 82
    assert result["trained"][80:] == ["pen", "flower"]
    assert result["detector"] == result["trained"]
    assert str(tmp_path) in result["folder"]  # the export sits beside the smoke weights

    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["mode"] == "full"
    assert metrics["epochs"] == 1
    assert metrics["names"] == NAMES
    assert set(metrics["val_own"]) == {"mAP50", "per_class"}
    assert metrics["coco"] is None
