"""The main window, offscreen, driving a real `PipelineWorker` on stub parts.

No test loads a model or opens a camera: the detector factory and the source
factory are stand-ins and the "camera" is a generator. The worker runs on the
window's own `QThread`, as in the app; every test closes the window, which
stops the worker and joins that thread.
"""

from __future__ import annotations

import os

# Before the first Qt import: never a window on the user's screen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from pathlib import Path

import numpy as np
import pytest
import shiboken6
from PySide6.QtCore import QPoint, Qt

import app
from conftest import config_text, schema_value
from core import events
from core.config import load_config
from core.types import Detection, Frame
from ui import main_window
from ui.main_window import MainWindow
from ui.worker import FramePayload, PipelineWorker

CONF = schema_value("model.conf")
CONF_DEBUG = schema_value("model.conf_debug")
FRAME_W, FRAME_H = 80, 60
FPS = 10.0
TIMEOUT_MS = 5000
NAMES = {0: "person", 1: "bottle"}
CAMERA_INDEX = 7
CAMERA = f"camera:{CAMERA_INDEX}"


def detection(cls_name: str, conf: float, bbox, dx: int, dy: int) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(
        cls_id=0, cls_name=cls_name, conf=conf, bbox=bbox,
        center=((x1 + x2) // 2, (y1 + y2) // 2), dx=dx, dy=dy,
        dx_pct=dx / (FRAME_W / 2), dy_pct=dy / (FRAME_H / 2),
    )


# Near the centre: the target until something else is clicked.
PERSON = detection("person", 0.95, (30.0, 20.0, 46.0, 36.0), -2, -2)
# Between conf_debug and conf: a near-miss until the slider goes below it.
BOTTLE = detection("bottle", round((CONF + CONF_DEBUG) / 2, 2), (2.0, 2.0, 12.0, 12.0), -33, -23)
# Far from the centre: a target only when clicked.
OTHER = detection("person", 0.9, (60.0, 40.0, 78.0, 58.0), 29, 19)


class StubDetector:
    def __init__(self, detections) -> None:
        self.detections = list(detections)

    @property
    def names(self) -> dict[int, str]:
        return dict(NAMES)

    def set_classes(self, classes) -> None:
        pass

    def __call__(self, frame: Frame) -> list[Detection]:
        return list(self.detections)


class FakeSource:
    """A `Source` stand-in: fixed frames, or an endless camera; counts `close()`."""

    def __init__(self, frames, *, is_stream=False, is_camera=False) -> None:
        self._frames = list(frames)
        self.is_stream = is_stream
        self.is_camera = is_camera
        self.fps = FPS if is_stream else 0.0
        self.frame_size = (FRAME_W, FRAME_H) if is_stream else None
        self.closed = 0

    def __len__(self) -> int:
        return 0 if self.is_camera else len(self._frames)

    def __iter__(self):
        if not self.is_camera:
            yield from self._frames
            return
        index = 0
        while not self.closed:
            yield frame(index, CAMERA)
            index += 1

    def close(self) -> None:
        self.closed += 1


def frame(index: int, source: str) -> Frame:
    return Frame(
        image=np.zeros((FRAME_H, FRAME_W, 3), np.uint8),
        source=source, index=index, time=index / FPS,
    )


RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [log]
"""


@pytest.fixture(autouse=True)
def empty_event_bus():
    events.clear()
    yield
    events.clear()


@pytest.fixture(autouse=True)
def warnings(monkeypatch):
    """Every `QMessageBox.warning` the window raises, instead of a modal box."""
    shown: list[str] = []

    class FakeBox:
        @staticmethod
        def warning(parent, title, text):
            shown.append(text)

    monkeypatch.setattr(main_window, "QMessageBox", FakeBox)
    return shown


@pytest.fixture
def out_dir(tmp_path) -> Path:
    return tmp_path / "out"


@pytest.fixture
def cfg(tmp_path, write_config, out_dir):
    weights = tmp_path / "stub.pt"
    weights.write_bytes(b"weights")
    rules = tmp_path / "rules.yaml"
    rules.write_text(RULES, encoding="utf-8")
    return load_config(write_config({
        "model.weights": weights.as_posix(),
        "classes": [],
        "display.color": False,
        "output.save_json": True,
        "output.save_image": True,
        "output.dir": out_dir.as_posix(),
        "rules.file": rules.as_posix(),
        "capture.camera": CAMERA_INDEX,
    }))


@pytest.fixture
def photos(tmp_path):
    folder = tmp_path / "photos"
    return FakeSource([frame(index, str(folder / f"p{index}.jpg")) for index in range(3)])


@pytest.fixture
def camera():
    return FakeSource([], is_stream=True, is_camera=True)


class LongVideo(FakeSource):
    """A video file long enough to still be running when the test acts on it."""

    def __init__(self, count: int) -> None:
        super().__init__([], is_stream=True)
        self._count = count

    def __len__(self) -> int:
        return self._count

    def __iter__(self):
        for index in range(self._count):
            if self.closed:
                return
            yield frame(index, "clip.mp4")


@pytest.fixture
def video():
    return LongVideo(1_000_000)


@pytest.fixture
def short_video():
    return LongVideo(5)


@pytest.fixture
def make_window(qtbot):
    """A window whose worker sees the given detections and sources; closed afterwards."""
    made: list[MainWindow] = []

    def build(cfg, detections, sources: dict, detector_error: Exception | None = None):
        def detector_factory(_cfg):
            if detector_error is not None:
                raise detector_error
            return StubDetector(detections)

        def worker_factory(session_cfg):
            return PipelineWorker(session_cfg, detector_factory, source_factory)

        def source_factory(spec, _cfg):
            if spec not in sources:
                raise ValueError(f"cannot open video: {spec}")
            return sources[spec]

        window = MainWindow(cfg, worker_factory)
        qtbot.addWidget(window)
        made.append(window)
        return window

    yield build
    for window in made:
        window.close()
        assert window.worker_thread.isFinished()


def wait_ready(qtbot, window):
    qtbot.waitUntil(lambda: window.open_file_button.isEnabled(), timeout=TIMEOUT_MS)


def column(window, name: str) -> int:
    headers = [window.table.horizontalHeaderItem(i).text()
               for i in range(window.table.columnCount())]
    return headers.index(name)


def cells(window, name: str) -> list[str]:
    col = column(window, name)
    return [window.table.item(row, col).text() for row in range(window.table.rowCount())]


# --- start and empty state ---------------------------------------------------------


def test_opening_a_photo_fills_the_table_with_drawn_objects_only(cfg, make_window, qtbot,
                                                                   photos):
    window = make_window(cfg, [PERSON, BOTTLE], {"photos": photos})
    wait_ready(qtbot, window)

    window.open_source("photos")
    qtbot.waitUntil(lambda: window.table.rowCount() > 0, timeout=TIMEOUT_MS)

    assert cells(window, "class") == ["person"]
    assert cells(window, "#id") == [""]
    assert cells(window, "conf") == ["0.95"]
    assert cells(window, "dx") == ["-2"]
    assert window.near_miss_label.text() == "1 near-miss below threshold (in the files only)"
    assert window.view.has_image()


def test_before_anything_opens_the_window_says_what_to_do(cfg, make_window, qtbot):
    window = make_window(cfg, [PERSON], {})
    assert window.windowTitle() == "Vision"
    assert window.view.placeholder == "Open a photo, a folder, a video or a camera"
    assert not window.view.has_image()
    assert window.no_objects_label.text() == "No objects"
    assert window.objects.currentWidget() is window.no_objects_label
    assert window.camera_box.value() == CAMERA_INDEX
    wait_ready(qtbot, window)
    assert window.open_folder_button.isEnabled() and window.open_camera_button.isEnabled()


def test_a_model_that_will_not_load_is_said_and_keeps_opening_disabled(cfg, make_window,
                                                                       qtbot, warnings):
    sentence = "run scripts/fetch_models.py first"
    window = make_window(cfg, [], {}, detector_error=FileNotFoundError(sentence))
    qtbot.waitUntil(lambda: warnings == [sentence], timeout=TIMEOUT_MS)
    for button in (window.open_file_button, window.open_folder_button,
                   window.open_camera_button):
        assert not button.isEnabled()


def test_a_source_that_fails_is_said_and_the_window_lives_on(cfg, make_window, qtbot,
                                                             warnings, photos):
    window = make_window(cfg, [PERSON], {"photos": photos})
    wait_ready(qtbot, window)
    window.open_source("broken.mp4")
    qtbot.waitUntil(lambda: warnings == ["cannot open video: broken.mp4"], timeout=TIMEOUT_MS)

    window.open_source("photos")
    qtbot.waitUntil(lambda: window.table.rowCount() == 1, timeout=TIMEOUT_MS)


# --- photos and folders ------------------------------------------------------------


def test_folder_steps_with_prev_and_next(cfg, make_window, qtbot, photos):
    window = make_window(cfg, [PERSON], {"photos": photos})
    wait_ready(qtbot, window)
    window.open_source("photos")
    qtbot.waitUntil(lambda: window.position_label.text() == "1 / 3", timeout=TIMEOUT_MS)
    assert not window.prev_button.isEnabled()

    window.next_button.click()
    qtbot.waitUntil(lambda: window.position_label.text() == "2 / 3", timeout=TIMEOUT_MS)
    window.next_button.click()
    qtbot.waitUntil(lambda: window.position_label.text() == "3 / 3", timeout=TIMEOUT_MS)
    assert not window.next_button.isEnabled()
    window.prev_button.click()
    qtbot.waitUntil(lambda: window.position_label.text() == "2 / 3", timeout=TIMEOUT_MS)
    assert "p1.jpg" in window.status_label.text()


# --- the confidence slider ----------------------------------------------------------


def test_slider_runs_from_conf_debug_to_one_and_starts_at_conf(cfg, make_window):
    window = make_window(cfg, [], {})
    assert window.slider.minimum() == round(CONF_DEBUG * 100)
    assert window.slider.maximum() == 100
    assert window.slider.value() == round(CONF * 100)
    assert window.slider_value.text() == f"{CONF:.2f}"
    assert f"{CONF_DEBUG:.2f}" in window.slider.toolTip()


def test_slider_redraws_a_photo_and_its_release_rewrites_the_files(cfg, make_window, qtbot,
                                                                   photos, out_dir):
    window = make_window(cfg, [PERSON, BOTTLE], {"photos": photos})
    wait_ready(qtbot, window)
    window.open_source("photos")
    qtbot.waitUntil(lambda: window.table.rowCount() == 1, timeout=TIMEOUT_MS)
    json_path = out_dir / "p0.json"
    qtbot.waitUntil(json_path.exists, timeout=TIMEOUT_MS)

    window.slider.setSliderDown(True)
    window.slider.setValue(window.slider.minimum())
    qtbot.waitUntil(lambda: window.table.rowCount() == 2, timeout=TIMEOUT_MS)
    assert window.slider_value.text() == f"{CONF_DEBUG:.2f}"
    assert window.near_miss_label.text().startswith("0 near-miss")

    def bottle_is_drawn() -> bool:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return [d["debug"] for d in data["detections"] if d["cls_name"] == "bottle"] == [False]

    assert not bottle_is_drawn()  # still held down: the files wait for the release
    window.slider.setSliderDown(False)  # emits sliderReleased
    qtbot.waitUntil(bottle_is_drawn, timeout=TIMEOUT_MS)


# --- streams -----------------------------------------------------------------------


def target_rows(window) -> list[int]:
    return [row for row, text in enumerate(cells(window, "#id")) if text.endswith("TARGET")]


def test_the_stream_target_row_is_marked(cfg, make_window, qtbot, video):
    window = make_window(cfg, [PERSON, OTHER, BOTTLE], {"clip.mp4": video})
    wait_ready(qtbot, window)
    window.open_source("clip.mp4")
    qtbot.waitUntil(lambda: len(target_rows(window)) == 1, timeout=TIMEOUT_MS)

    row = target_rows(window)[0]
    assert cells(window, "dx")[row] == "-2"
    assert cells(window, "#id")[row].startswith("#")
    assert sorted(cells(window, "class")) == ["person", "person"]
    assert "FPS" in window.status_label.text()


def test_a_click_in_the_view_locks_the_object_under_it(cfg, make_window, qtbot, video):
    window = make_window(cfg, [PERSON, OTHER], {"clip.mp4": video})
    # 480x300 fits the 80x60 frame at scale 5: 400 wide, 40-pixel bars left and right.
    window.view.setFixedSize(480, 300)
    window.show()
    qtbot.waitExposed(window)
    wait_ready(qtbot, window)
    window.open_source("clip.mp4")
    qtbot.waitUntil(lambda: len(target_rows(window)) == 1, timeout=TIMEOUT_MS)
    window.toggle_pause()
    assert window.pause_button.text() == "Resume"

    # The centre of OTHER is (69, 49) in the frame: 40 + 69 * 5, 0 + 49 * 5 in the widget.
    qtbot.mouseClick(window.view, Qt.MouseButton.LeftButton, pos=QPoint(385, 245))

    qtbot.waitUntil(lambda: [cells(window, "dx")[r] for r in target_rows(window)] == ["+29"],
                    timeout=TIMEOUT_MS)


def test_a_frame_queued_by_the_old_source_never_shows_under_the_new_one(cfg, make_window,
                                                                        qtbot, photos):
    window = make_window(cfg, [PERSON], {"photos": photos})
    wait_ready(qtbot, window)
    window.open_source("photos")
    qtbot.waitUntil(lambda: window.table.rowCount() == 1, timeout=TIMEOUT_MS)
    shown: list[int] = []
    show_image = window.view.show_image
    window.view.show_image = lambda canvas: (shown.append(int(canvas[0, 0, 0])),
                                             show_image(canvas))

    window.open_source("photos")
    # A frame the old source queued before the worker reached the new open.
    stale = FramePayload(
        canvas=np.full((FRAME_H, FRAME_W, 3), 255, np.uint8), drawn=[OTHER, OTHER],
        near_miss_count=9, target_track_id=None, index=0, total=1, fps=FPS,
        source="clip.mp4", is_stream=True,
    )
    window.worker.frame_ready.emit(stale)
    qtbot.waitUntil(lambda: shown != [], timeout=TIMEOUT_MS)
    qtbot.wait(50)

    assert 255 not in shown
    assert cells(window, "dx") == ["-2"]
    assert window.near_miss_label.text().startswith("0 near-miss")


def test_a_finished_video_leaves_the_summary_and_its_events(cfg, make_window, qtbot,
                                                            short_video):
    window = make_window(cfg, [PERSON], {"clip.mp4": short_video})
    wait_ready(qtbot, window)
    window.open_source("clip.mp4")
    qtbot.waitUntil(lambda: window.status_label.text().startswith("5 frames, 1 events"),
                    timeout=TIMEOUT_MS)
    assert "person_appeared" in window.events_list.toPlainText()
    assert window.view.has_image()
    assert not window.pause_button.isEnabled()
    assert short_video.closed == 1


def test_closing_the_window_releases_the_camera_and_ends_the_thread(cfg, make_window, qtbot,
                                                                    camera):
    window = make_window(cfg, [PERSON], {CAMERA: camera})
    wait_ready(qtbot, window)
    window.open_camera_button.click()
    qtbot.waitUntil(lambda: CAMERA in window.status_label.text(), timeout=TIMEOUT_MS)
    assert not window.pause_button.isEnabled()  # a camera cannot be paused

    window.close()

    assert window.worker_thread.isFinished()
    assert camera.closed == 1
    # The worker went with its thread (deleteLater on `finished`).
    qtbot.waitUntil(lambda: not shiboken6.isValid(window.worker), timeout=TIMEOUT_MS)


# --- the entry point -----------------------------------------------------------------


def test_app_help_works(capsys):
    with pytest.raises(SystemExit) as exit_info:
        app.main(["--help"])
    assert exit_info.value.code == 0
    assert "--source" in capsys.readouterr().out


@pytest.mark.parametrize("broken_text", [
    "model: [\n",  # not YAML at all
    config_text(without=("model.conf",)),  # parses, but a key is missing: ConfigError
])
def test_a_broken_config_is_one_sentence_and_no_window(tmp_path, monkeypatch, capsys,
                                                       broken_text):
    broken = tmp_path / "config.yaml"
    broken.write_text(broken_text, encoding="utf-8")
    monkeypatch.setattr(app, "CONFIG_PATH", broken)

    def no_window(*args, **kwargs):
        raise AssertionError("a window was opened")

    monkeypatch.setattr(main_window, "MainWindow", no_window)

    assert app.main([]) == app.EXIT_USAGE
    err = capsys.readouterr().err.strip()
    assert err and "\n" not in err
