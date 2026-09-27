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
from PySide6.QtWidgets import QLabel

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
MISSING_WEIGHTS = "run scripts/fetch_models.py first"


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
        unknown = sorted(set(classes) - set(NAMES.values()))
        if unknown:  # the sentence the real Detector gives
            raise ValueError(f"unknown class names in config: {', '.join(unknown)}")

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


@pytest.fixture(scope="module", autouse=True)
def tracker_imported():
    """Pay the tracker's one-time import (about 3 s) before any wait starts counting.

    `Tracker.__init__` imports Ultralytics' ByteTrack lazily, so the first stream
    in the process would spend most of TIMEOUT_MS on it under a loaded CPU.
    """
    import core.detector  # noqa: F401 -- the offline switches first, as core.tracker does
    from ultralytics.engine.results import Boxes  # noqa: F401
    from ultralytics.trackers.byte_tracker import BYTETracker  # noqa: F401


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

    def build(cfg, detections, sources: dict, detector_error: Exception | None = None,
              failing_weights: tuple[str, ...] = ()):
        def detector_factory(model_cfg):
            if detector_error is not None:
                raise detector_error
            if Path(model_cfg.model.weights).name in failing_weights:
                raise FileNotFoundError(MISSING_WEIGHTS)
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
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False  # read while the worker was rewriting it
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


# --- the settings panel ---------------------------------------------------------------


@pytest.fixture
def models_dir(tmp_path, monkeypatch) -> Path:
    """A `models\\` folder of its own: `good.pt` loads, `missing.pt` does not."""
    folder = tmp_path / "models"
    folder.mkdir()
    for name in ("good.pt", "missing.pt"):
        (folder / name).write_bytes(b"weights")
    monkeypatch.setattr(main_window, "MODELS_DIR", folder)
    return folder


def test_the_panel_is_in_the_window_and_a_change_goes_to_the_worker_at_once(cfg, make_window,
                                                                            qtbot):
    window = make_window(cfg, [PERSON], {})
    assert window.settings.parent() is window.settings_area
    wait_ready(qtbot, window)
    # model_ready fills the class list with the model's names.
    assert [window.settings.classes_list.item(i).text()
            for i in range(window.settings.classes_list.count())] == ["person", "bottle"]

    assert window.table.isColumnHidden(column(window, "colour"))

    window.settings.color_check.setChecked(True)

    # The column follows the worker's `applied`: the config really reached the worker.
    # (Not qtbot.waitSignal on the worker: its callback runs on the worker's thread,
    # ahead of the window's queued slot.)
    qtbot.waitUntil(lambda: not window.table.isColumnHidden(column(window, "colour")),
                    timeout=TIMEOUT_MS)


def test_a_model_that_will_not_load_leaves_the_old_one_in_the_panel(cfg, make_window, qtbot,
                                                                   warnings, models_dir):
    window = make_window(cfg, [PERSON], {}, failing_weights=("missing.pt",))
    wait_ready(qtbot, window)
    before = window.settings.model_box.currentText()

    window.settings.model_box.setCurrentText("models/missing.pt")
    assert window.status_label.text() == "Loading model…"

    qtbot.waitUntil(lambda: warnings == [MISSING_WEIGHTS], timeout=TIMEOUT_MS)
    qtbot.waitUntil(lambda: window.settings.model_box.currentText() == before,
                    timeout=TIMEOUT_MS)
    assert window.status_label.text() != "Loading model…"
    assert window.open_file_button.isEnabled()  # the old model still runs


def test_without_weights_the_panel_still_works_and_another_model_can_be_chosen(
        cfg, make_window, qtbot, warnings, models_dir):
    window = make_window(cfg, [PERSON], {}, failing_weights=(Path(cfg.model.weights).name,))
    qtbot.waitUntil(lambda: warnings == [MISSING_WEIGHTS], timeout=TIMEOUT_MS)
    assert not window.open_file_button.isEnabled()
    assert window.settings.isEnabled()

    window.settings.model_box.setCurrentText("models/good.pt")

    wait_ready(qtbot, window)
    assert window.settings.classes_list.count() == len(NAMES)


def test_a_class_the_model_does_not_know_is_said_and_the_panel_goes_back(
        tmp_path, write_config, make_window, qtbot, warnings):
    weights = tmp_path / "stub.pt"
    weights.write_bytes(b"weights")
    cfg = load_config(write_config({"model.weights": weights.as_posix(), "classes": ["ghost"]}))
    window = make_window(cfg, [PERSON], {})
    wait_ready(qtbot, window)
    panel = window.settings
    person = panel.classes_list.findItems("person", Qt.MatchFlag.MatchExactly)[0]

    person.setCheckState(Qt.CheckState.Checked)

    qtbot.waitUntil(lambda: warnings == ["unknown class names in config: ghost"],
                    timeout=TIMEOUT_MS)
    qtbot.waitUntil(lambda: panel.config().classes == ["ghost"], timeout=TIMEOUT_MS)
    person = panel.classes_list.findItems("person", Qt.MatchFlag.MatchExactly)[0]
    assert person.checkState() == Qt.CheckState.Unchecked


# --- Save to config.yaml ---------------------------------------------------------------


@pytest.fixture
def config_copy(cfg, tmp_path, monkeypatch) -> Path:
    """The test config with comments added; the window saves into it, never the real one."""
    path = tmp_path / "config.yaml"  # where `cfg` came from
    text = path.read_text(encoding="utf-8")
    conf_line = f"  conf: {CONF}\n"
    assert text.count(conf_line) == 1
    text = "# Vision settings\n" + text.replace(conf_line, f"  conf: {CONF}  # threshold\n")
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(main_window, "CONFIG_PATH", path)
    return path


def changed_lines(before: bytes, after: bytes) -> list[tuple[str, str]]:
    old, new = before.decode("utf-8").splitlines(), after.decode("utf-8").splitlines()
    assert len(old) == len(new)
    return [(a, b) for a, b in zip(old, new) if a != b]


def test_save_writes_only_what_changed_and_keeps_the_rest_of_the_file(config_copy, make_window,
                                                                      qtbot):
    before = config_copy.read_bytes()
    cfg = load_config(config_copy)
    window = make_window(cfg, [PERSON], {})
    wait_ready(qtbot, window)
    new_conf = window.slider.value() + 3
    window.slider.setValue(new_conf)
    colour = not cfg.display.color
    window.settings.color_check.setChecked(colour)
    qtbot.waitUntil(lambda: window.table.isColumnHidden(column(window, "colour")) is not colour,
                    timeout=TIMEOUT_MS)  # the worker has applied it

    window.settings.save_button.click()

    assert window.notice_label.text() == "Saved: model.conf, display.color"
    changes = changed_lines(before, config_copy.read_bytes())
    assert [old.split(":")[0].strip() for old, _ in changes] == ["conf", "color"]
    assert f"conf: {new_conf / 100}" in changes[0][1]
    assert "#" in changes[0][1]  # the trailing comment stays
    saved = load_config(config_copy)
    assert saved.model.conf == new_conf / 100
    assert saved.display.color is colour


def test_save_with_nothing_changed_says_so_and_leaves_the_file(config_copy, make_window, qtbot):
    before = config_copy.read_bytes()
    window = make_window(load_config(config_copy), [PERSON], {})
    wait_ready(qtbot, window)

    window.settings.save_button.click()

    assert window.notice_label.text() == "Nothing to save"
    assert config_copy.read_bytes() == before


def status_bar_texts(window) -> list[str]:
    return [label.text() for label in window.statusBar().findChildren(QLabel)]


def test_the_save_result_stays_readable_while_a_video_runs(config_copy, make_window, qtbot,
                                                           video):
    window = make_window(load_config(config_copy), [PERSON], {"clip.mp4": video})
    wait_ready(qtbot, window)
    window.open_source("clip.mp4")
    qtbot.waitUntil(lambda: "FPS" in window.status_label.text(), timeout=TIMEOUT_MS)

    window.settings.save_button.click()
    shown = window.status_label.text()
    qtbot.waitUntil(lambda: window.status_label.text() != shown, timeout=TIMEOUT_MS)
    qtbot.wait(300)  # frames keep coming

    assert "Nothing to save" in status_bar_texts(window)


def test_save_right_after_a_panel_change_saves_the_new_value(config_copy, make_window, qtbot):
    cfg = load_config(config_copy)
    window = make_window(cfg, [PERSON], {})
    wait_ready(qtbot, window)

    # No event loop turn in between: the worker has not answered `applied` yet.
    window.settings.center_line_check.setChecked(not cfg.display.center_line)
    window.settings.save_button.click()

    assert load_config(config_copy).display.center_line is (not cfg.display.center_line)


def test_a_model_chosen_before_the_last_one_was_applied_still_says_loading(
        cfg, make_window, qtbot, models_dir):
    window = make_window(cfg, [PERSON], {})
    wait_ready(qtbot, window)
    before = window.settings.model_box.currentText()
    window.settings.model_box.setCurrentText("models/good.pt")
    # The new model's `model_ready` has been handled, its `applied` not yet.
    window.worker.model_ready.emit(dict(NAMES))
    assert window.status_label.text() != main_window.LOADING_TEXT

    window.settings.model_box.setCurrentText(before)  # back: another reload

    assert window.status_label.text() == main_window.LOADING_TEXT
    qtbot.waitUntil(lambda: window.status_label.text() != main_window.LOADING_TEXT,
                    timeout=TIMEOUT_MS)


def test_save_into_a_broken_file_is_said_and_changes_nothing(config_copy, make_window, qtbot,
                                                             warnings):
    window = make_window(load_config(config_copy), [PERSON], {})
    wait_ready(qtbot, window)
    window.slider.setValue(window.slider.value() + 3)
    broken = config_copy.read_bytes().replace(b"  conf_debug:", b"  #conf_debug:")
    config_copy.write_bytes(broken)

    window.settings.save_button.click()

    assert len(warnings) == 1 and "conf_debug" in warnings[0]
    assert config_copy.read_bytes() == broken


def test_save_into_a_file_that_is_not_yaml_says_the_apps_sentence(config_copy, make_window,
                                                                 qtbot, warnings):
    window = make_window(load_config(config_copy), [PERSON], {})
    wait_ready(qtbot, window)
    config_copy.write_text("model: [\n", encoding="utf-8")

    window.settings.save_button.click()

    assert warnings == [app.not_yaml_text(config_copy)]
    assert config_copy.read_text(encoding="utf-8") == "model: [\n"


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
