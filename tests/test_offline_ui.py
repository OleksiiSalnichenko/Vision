"""The offline guarantee, desktop half: the app detects a photo without the network.

A child process traps every socket, starts Qt offscreen, builds `MainWindow`
with the app's own worker (`app.make_worker`: the real `Detector` on the model
`config.yaml` names, the real `Source`), opens `data/test_images/bus.jpg`,
waits for the frame and closes the window. Nothing may resolve a name or open a
connection on the way.

It is a subprocess for the reasons `tests/test_offline.py` gives: Ultralytics
freezes its online flag at the first import in a process and mutes its own
telemetry under pytest, so an in-process run would pass whatever the project
did. Only the output folder is redirected, to a temporary one; the real
`out\\` is left alone.
"""

import dataclasses
import json
import os
import subprocess
import sys

import pytest

from conftest import PROJECT_ROOT
from core.config import load_config
from core.detector import require_weights
from detect import CONFIG_PATH

PHOTO = PROJECT_ROOT / "data" / "test_images" / "bus.jpg"

CHILD = r"""
import json, os, socket, sys, time

calls = []


def trap(name, answer):
    def call(*args, **kwargs):
        calls.append(name)
        if isinstance(answer, Exception):
            raise answer
        return answer
    return call


socket.getaddrinfo = trap(
    "getaddrinfo", [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
)
socket.create_connection = trap("create_connection", OSError("blocked by test"))
socket.gethostbyname = trap("gethostbyname", "127.0.0.1")
socket.socket.connect = trap("connect", OSError("blocked by test"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
project, photo, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, project)

import dataclasses

import app  # imports core.detector first, as the real entry point does
from core.config import load_config
from detect import CONFIG_PATH

from PySide6.QtWidgets import QApplication

from ui import main_window

warnings = []


class Box:
    @staticmethod
    def warning(parent, title, text):
        warnings.append(text)


main_window.QMessageBox = Box

cfg = load_config(CONFIG_PATH)
cfg = dataclasses.replace(cfg, output=dataclasses.replace(cfg.output, dir=out_dir))
qt_app = QApplication([])
window = main_window.MainWindow(cfg, app.make_worker)
window.open_source(photo)  # queued behind the model load, as app.py --source does

deadline = time.monotonic() + 240
while time.monotonic() < deadline and not warnings:
    qt_app.processEvents()
    if window.view.has_image() and os.path.basename(photo) in window.status_label.text():
        break
    time.sleep(0.02)

shown = window.view.has_image()
rows = window.tree.topLevelItemCount()
window.close()

print(json.dumps({
    "calls": calls,
    "warnings": warnings,
    "shown": shown,
    "rows": rows,
    "json_written": os.path.exists(os.path.join(out_dir, "bus.json")),
}))
"""


def _weights_ready() -> str | None:
    """Why the real model cannot be loaded here, or None when it can."""
    cfg = load_config(CONFIG_PATH)
    weights = PROJECT_ROOT / cfg.model.weights  # an absolute path stays itself
    try:
        require_weights(dataclasses.replace(
            cfg, model=dataclasses.replace(cfg.model, weights=str(weights))
        ))
    except FileNotFoundError as err:
        return f"no model on disk ({err})"
    return None


def test_the_app_detects_a_photo_without_touching_the_network(tmp_path):
    reason = _weights_ready()
    if reason:
        pytest.skip(reason)
    if not PHOTO.is_file():
        pytest.skip(f"no test photo: {PHOTO} (run scripts/fetch_models.py)")

    env = dict(os.environ)
    # None of these may pass the test on the project's behalf.
    for name in ("PYTEST_CURRENT_TEST", "YOLO_OFFLINE", "CI", "TF_BUILD", "JENKINS_URL"):
        env.pop(name, None)
    out_dir = tmp_path / "out"

    done = subprocess.run(
        [sys.executable, "-c", CHILD, str(PROJECT_ROOT), str(PHOTO), str(out_dir)],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, f"child failed:\n{done.stdout}\n{done.stderr}"
    result = json.loads(done.stdout.strip().splitlines()[-1])

    assert result["warnings"] == []
    assert result["shown"] is True
    assert result["rows"] > 0  # bus.jpg holds people and a bus
    assert result["json_written"] is True
    assert result["calls"] == [], f"network reached by the app: {result['calls']}"
