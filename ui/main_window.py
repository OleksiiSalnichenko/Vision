"""The main window: sources, the live view, the threshold, the object list, events.

The window only draws and forwards. Every command goes to the `PipelineWorker`
through a queued signal -- the worker lives on its own `QThread` and owns the
model, the source and the stream session -- and every frame comes back as a
`FramePayload`. The window says `frame_shown` back for every payload it has
done with, and the worker sends nothing new until then, so an unpaced video
never floods this thread's queue; only the newest frame is shown, and the
worker still writes every frame to the files. The
paint is requested as a queued call, not a zero timer: Qt drains posted events
before it fires timers, so a timer would starve under a flood of frames.

Every open goes through `_OpenRelay` on the worker's thread, which says
`opening(n)` back just before the worker opens the source. Frames the old
source queued before that line are dropped, never shown under the new one.

The window owns its worker thread; the worker is created by the factory, moved
onto that thread, and deleted there (`deleteLater` on `finished`). Closing the
window stops the worker and waits for its thread to end, so a camera is
released before the window is gone.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QBrush, QCloseEvent, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config import Config, ConfigError, load_config, save_values
from core.source import CAMERA_PREFIX, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from core.types import Detection
from detect import CONFIG_PATH, PROJECT_ROOT
from ui.settings_panel import SettingsPanel, model_entry
from ui.view import FrameView
from ui.worker import FramePayload, PipelineWorker

MODELS_DIR = PROJECT_ROOT / "models"

WINDOW_TITLE = "Vision"
EMPTY_VIEW_TEXT = "Open a photo, a folder, a video or a camera"
NO_OBJECTS_TEXT = "No objects"
LOADING_TEXT = "Loading model…"
TARGET_MARK = "TARGET"
COLUMNS = ("#id", "class", "conf", "dx", "dy", "dx %", "dy %", "colour")
_COLOUR_COLUMN = COLUMNS.index("colour")
MODEL_READY_TEXT = "Model ready"
NOTHING_TO_SAVE_TEXT = "Nothing to save"

# Presentation constants: the slider works in hundredths, the window's first size.
_SLIDER_SCALE = 100
_SLIDER_PAGE_STEP = 5  # hundredths per Page Up / Page Down
_WINDOW_SIZE = (1280, 800)
_CAMERA_MAX = 99
_NOTICE_MS = 5000  # how long a one-off result ("Saved: ...") stays in the status bar
_TARGET_BRUSH = QBrush(Qt.GlobalColor.magenta)
_TARGET_TEXT = QBrush(Qt.GlobalColor.white)


def near_miss_text(count: int) -> str:
    return f"{count} near-miss below threshold (in the files only)"


def unsaved_values(session: Config, on_disk: Config, models_dir: str | Path) -> dict[str, Any]:
    """The settings the window can change whose session value differs from the file's.

    Keys are `model.weights`, `model.imgsz`, `model.conf`, `classes`,
    `display.center_line`, `display.color`, in that order, as `save_values` takes them.

    The weights compare in the model list's one spelling, so `./models/a.pt`
    in the file is not a change against `models/a.pt` in the session; the
    threshold compares in the slider's hundredths, so a file value the slider
    can only show rounded is not a change either.
    """
    values: dict[str, Any] = {}
    if model_entry(models_dir, session.model.weights) != \
            model_entry(models_dir, on_disk.model.weights):
        values["model.weights"] = session.model.weights
    if session.model.imgsz != on_disk.model.imgsz:
        values["model.imgsz"] = session.model.imgsz
    conf = round(session.model.conf * _SLIDER_SCALE)
    if conf != round(on_disk.model.conf * _SLIDER_SCALE):
        values["model.conf"] = conf / _SLIDER_SCALE
    if list(session.classes) != list(on_disk.classes):
        values["classes"] = list(session.classes)
    if session.display.center_line != on_disk.display.center_line:
        values["display.center_line"] = session.display.center_line
    if session.display.color != on_disk.display.color:
        values["display.color"] = session.display.color
    return values


def saved_text(keys) -> str:
    keys = list(keys)
    return f"Saved: {', '.join(keys)}" if keys else NOTHING_TO_SAVE_TEXT


def file_filter() -> str:
    """The "Open file…" filter: every photo and video extension `core.source` reads."""
    patterns = " ".join(f"*{ext}" for ext in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS)
    photos = " ".join(f"*{ext}" for ext in IMAGE_EXTENSIONS)
    videos = " ".join(f"*{ext}" for ext in VIDEO_EXTENSIONS)
    return f"Photos and videos ({patterns});;Photos ({photos});;Videos ({videos})"


class _OpenRelay(QObject):
    """Lives on the worker's thread: marks where the old source's frames end, then opens.

    Its `opening(n)` is emitted from the worker's thread before `open_source`
    runs, so it reaches the window after every frame of the old source and
    before any frame of the new one.
    """

    opening = Signal(int)

    def __init__(self, worker: PipelineWorker) -> None:
        super().__init__(worker)  # a child moves with the worker and dies with it
        self._worker = worker

    @Slot(int, str)
    def open(self, generation: int, spec: str) -> None:
        self.opening.emit(generation)
        self._worker.open_source(spec)


class MainWindow(QMainWindow):
    """The Vision window. `worker_factory(cfg)` builds the `PipelineWorker` it drives."""

    # Commands to the worker; queued, since the worker lives on its own thread.
    _load_model = Signal()
    _open = Signal(int, str)
    _present_requested = Signal()
    _stop = Signal()
    _shutdown = Signal()
    _pause = Signal(bool)
    _click = Signal(float, float)
    _set_conf = Signal(float)
    _commit_still = Signal()
    _show_index = Signal(int)
    _apply = Signal(object)
    _frame_shown = Signal()

    def __init__(self, cfg: Config, worker_factory: Callable[[Config], PipelineWorker],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cfg = cfg  # what the worker last said the session runs on
        # What the panel last sent: ahead of `_cfg` until the worker answers every apply.
        self._sent = cfg
        self._applies_pending = 0
        self._model_loaded = False
        self._payload: FramePayload | None = None  # the frame on screen
        self._pending: FramePayload | None = None  # the newest frame not yet painted
        self._paused = False
        self._streaming = False  # a stream is running: its end says `finished`
        self._generation = 0  # bumped on every open
        self._live_generation = 0  # the open whose frames the worker now sends
        self._shown_generation = 0  # the open the frame on screen belongs to
        self._loading = True  # a model is loading: its answer puts the status back
        self._status_before_loading = ""

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*_WINDOW_SIZE)
        self._build(cfg)

        self.worker = worker_factory(cfg)
        self.worker_thread = QThread(self)
        self._relay = _OpenRelay(self.worker)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self._wire()
        self.worker_thread.start()
        self._set_open_enabled(False)
        self._set_status(LOADING_TEXT)
        self._load_model.emit()

    # --- layout -------------------------------------------------------------------

    def _build(self, cfg: Config) -> None:
        self.open_file_button = QPushButton("Open file…")
        self.open_folder_button = QPushButton("Open folder…")
        self.camera_box = QSpinBox()
        self.camera_box.setRange(0, _CAMERA_MAX)
        self.camera_box.setValue(cfg.capture.camera)
        self.camera_box.setToolTip("Camera number")
        self.open_camera_button = QPushButton("Open camera")
        self.stop_button = QPushButton("Stop")
        self.pause_button = QPushButton("Pause")
        self.prev_button = QPushButton("◀ Prev")
        self.next_button = QPushButton("Next ▶")
        self.position_label = QLabel("")
        for button in (self.stop_button, self.pause_button, self.prev_button, self.next_button):
            button.setEnabled(False)
        for button in (self.open_file_button, self.open_folder_button, self.open_camera_button,
                       self.stop_button, self.pause_button, self.prev_button, self.next_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the space bar is Pause

        sources = QHBoxLayout()
        for widget in (self.open_file_button, self.open_folder_button, QLabel("Camera"),
                       self.camera_box, self.open_camera_button, self.stop_button,
                       self.pause_button, self.prev_button, self.position_label,
                       self.next_button):
            sources.addWidget(widget)
        sources.addStretch(1)

        self.view = FrameView(EMPTY_VIEW_TEXT)

        low = round(cfg.model.conf_debug * _SLIDER_SCALE)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(low, _SLIDER_SCALE)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(_SLIDER_PAGE_STEP)
        self.slider.setValue(round(cfg.model.conf * _SLIDER_SCALE))
        self.slider.setToolTip(
            f"The model runs at model.conf_debug = {cfg.model.conf_debug:.2f}: "
            "nothing below it exists, so the slider stops there"
        )
        self.slider_value = QLabel(self._conf_text(self.slider.value()))
        threshold = QHBoxLayout()
        threshold.addWidget(QLabel("Confidence"))
        threshold.addWidget(self.slider, 1)
        threshold.addWidget(self.slider_value)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(_COLOUR_COLUMN, not cfg.display.color)
        self.no_objects_label = QLabel(NO_OBJECTS_TEXT)
        self.no_objects_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.objects = QStackedWidget()
        self.objects.addWidget(self.no_objects_label)
        self.objects.addWidget(self.table)
        self.near_miss_label = QLabel(near_miss_text(0))

        self.events_list = QPlainTextEdit()
        self.events_list.setReadOnly(True)

        side = QVBoxLayout()
        side.addWidget(QLabel("Objects"))
        side.addWidget(self.objects, 2)
        side.addWidget(self.near_miss_label)
        side.addWidget(QLabel("Events"))
        side.addWidget(self.events_list, 1)
        side_widget = QWidget()
        side_widget.setLayout(side)

        # Always shown and always enabled: with no model loaded it is how another is chosen.
        self.settings_area = QWidget()
        settings_layout = QVBoxLayout(self.settings_area)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(QLabel("Settings"))
        self.settings = SettingsPanel(cfg, MODELS_DIR)
        settings_layout.addWidget(self.settings)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        viewer = QWidget()
        viewer_layout = QVBoxLayout(viewer)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.addWidget(self.view, 1)
        viewer_layout.addLayout(threshold)
        splitter.addWidget(viewer)
        splitter.addWidget(side_widget)
        splitter.addWidget(self.settings_area)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(sources)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.status_label = QLabel("")
        self.statusBar().addWidget(self.status_label, 1)
        # One-off results ("Saved: ...") get their own label: the next frame cannot
        # overwrite them, and they clear themselves after a few seconds.
        self.notice_label = QLabel("")
        self.statusBar().addPermanentWidget(self.notice_label)
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.setInterval(_NOTICE_MS)
        self._notice_timer.timeout.connect(self.notice_label.clear)

        self.open_file_button.clicked.connect(self._choose_file)
        self.open_folder_button.clicked.connect(self._choose_folder)
        self.open_camera_button.clicked.connect(self._open_camera)
        self.stop_button.clicked.connect(self._stop.emit)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.prev_button.clicked.connect(lambda: self._step_photo(-1))
        self.next_button.clicked.connect(lambda: self._step_photo(+1))
        self.slider.valueChanged.connect(self._slider_moved)
        self.slider.sliderReleased.connect(self._slider_released)
        self.view.clicked.connect(self._view_clicked)
        self.settings.changed.connect(self._settings_changed)
        self.settings.save_requested.connect(self._save)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_pause)

    def _wire(self) -> None:
        worker = self.worker
        self._load_model.connect(worker.load_model)
        self._open.connect(self._relay.open)
        self._relay.opening.connect(self._opening)
        self._present_requested.connect(self._present, Qt.ConnectionType.QueuedConnection)
        self._stop.connect(worker.stop)
        self._shutdown.connect(worker.shutdown)
        self._pause.connect(worker.set_paused)
        self._click.connect(worker.click)
        self._set_conf.connect(worker.set_conf)
        self._commit_still.connect(worker.commit_still)
        self._show_index.connect(worker.show_index)
        self._apply.connect(worker.apply)
        self._frame_shown.connect(worker.frame_shown)
        worker.model_ready.connect(self._model_ready)
        worker.model_failed.connect(self._model_failed)
        worker.frame_ready.connect(self._frame_ready)
        worker.event.connect(self._event)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.applied.connect(self._applied)

    # --- commands -----------------------------------------------------------------

    def open_source(self, spec: str) -> None:
        """Open `spec` (the `detect.py --source` format); the worker stops the old one."""
        if self._pending is not None:
            self._pending = None
            self._frame_shown.emit()  # never painted, but the worker must not wait for it
        self._paused = False
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._generation += 1
        self._open.emit(self._generation, spec)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open file", "", file_filter())
        if path:
            self.open_source(str(Path(path)))

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open folder")
        if path:
            self.open_source(str(Path(path)))

    def _open_camera(self) -> None:
        self.open_source(f"{CAMERA_PREFIX}{self.camera_box.value()}")

    def toggle_pause(self) -> None:
        """Pause or resume a video file; nothing else can be paused."""
        if not self.pause_button.isEnabled():
            return
        self._paused = not self._paused
        self.pause_button.setText("Resume" if self._paused else "Pause")
        self._pause.emit(self._paused)

    def _step_photo(self, step: int) -> None:
        payload = self._payload
        if payload is None or payload.is_stream:
            return
        index = payload.index + step
        if 0 <= index < payload.total:
            self._show_index.emit(index)

    def _view_clicked(self, x: float, y: float) -> None:
        if self._payload is not None and self._payload.is_stream:
            self._click.emit(x, y)

    def _slider_moved(self, value: int) -> None:
        self.slider_value.setText(self._conf_text(value))
        self._set_conf.emit(value / _SLIDER_SCALE)
        if not self.slider.isSliderDown():
            # A key or the wheel: one step is one final value.
            self._commit_photo()

    def _slider_released(self) -> None:
        self._commit_photo()

    def _commit_photo(self) -> None:
        if self._payload is not None and not self._payload.is_stream:
            self._commit_still.emit()

    def _settings_changed(self, cfg: Config) -> None:
        """A panel change goes to the worker at once; a new model or imgsz reloads it."""
        old = self._sent.model
        if (cfg.model.weights, cfg.model.imgsz) != (old.weights, old.imgsz):
            if not self._loading:
                self._status_before_loading = self.status_label.text()
            self._loading = True
            self._set_status(LOADING_TEXT)
        self._sent = cfg
        self._applies_pending += 1
        self._apply.emit(cfg)

    def _session_config(self) -> Config:
        """The config the panel last sent, with the threshold the slider shows."""
        conf = self.slider.value() / _SLIDER_SCALE
        return dataclasses.replace(self._sent, model=dataclasses.replace(self._sent.model, conf=conf))

    def _save(self) -> None:
        """Write the settings that differ from `config.yaml` into it; nothing else changes."""
        try:
            values = unsaved_values(self._session_config(), load_config(CONFIG_PATH), MODELS_DIR)
            if values:
                save_values(CONFIG_PATH, values)
        except (ConfigError, OSError) as err:
            self._warn(str(err))
            return
        self._notice(saved_text(values))

    def _end_loading(self) -> None:
        if self._loading:
            self._loading = False
            self._set_status(self._status_before_loading or MODEL_READY_TEXT)

    @staticmethod
    def _conf_text(value: int) -> str:
        return f"{value / _SLIDER_SCALE:.2f}"

    # --- what the worker says ----------------------------------------------------

    def _model_ready(self, names: dict) -> None:
        self._model_loaded = True
        self._set_open_enabled(True)
        self.settings.set_class_names(names)
        self._end_loading()

    def _model_failed(self, sentence: str) -> None:
        # After a failed switch the old model keeps running (the worker's
        # `applied` puts it back in the panel); only a model that never loaded
        # leaves nothing to open a source with.
        self._end_loading()
        if not self._model_loaded:
            self._set_open_enabled(False)
            self._set_status(sentence)
        self._warn(sentence)

    def _opening(self, generation: int) -> None:
        self._live_generation = generation

    def _frame_ready(self, payload: FramePayload) -> None:
        if self._live_generation != self._generation:
            self._frame_shown.emit()  # done with it: queued by a source already left
            return
        # Keep only the newest; one paint per queued request, never starved.
        first = self._pending is None
        if not first:
            self._frame_shown.emit()  # the one it replaces will never be painted
        self._pending = payload
        if first:
            self._present_requested.emit()

    def _present(self) -> None:
        payload, self._pending = self._pending, None
        if payload is None:
            return
        self._payload = payload
        self._shown_generation = self._live_generation
        self._streaming = payload.is_stream
        self.view.show_image(payload.canvas)
        self._fill_table(payload.drawn, payload.target_track_id)
        self.near_miss_label.setText(near_miss_text(payload.near_miss_count))
        self.pause_button.setEnabled(payload.is_stream and payload.total > 0)
        stills = not payload.is_stream
        self.prev_button.setEnabled(stills and payload.index > 0)
        self.next_button.setEnabled(stills and payload.index + 1 < payload.total)
        self.position_label.setText(
            f"{payload.index + 1} / {payload.total}" if stills and payload.total > 1 else ""
        )
        self._set_status(self._status_text(payload))
        self._frame_shown.emit()  # painted: the worker may send the next one

    def _event(self, line: str) -> None:
        self.events_list.appendPlainText(line)
        bar = self.events_list.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _failed(self, sentence: str) -> None:
        if self._shown_generation != self._generation:
            # The open failed before its first frame; the worker already stopped the
            # source on screen, so its picture and table would only mislead.
            self._payload = None
            self.view.clear()
            self._fill_table([], None)
            self.near_miss_label.setText(near_miss_text(0))
            for button in (self.stop_button, self.pause_button, self.prev_button,
                           self.next_button):
                button.setEnabled(False)
            self.position_label.setText("")
            self._set_status(sentence)
        self._warn(sentence)

    def _finished(self, summary: str) -> None:
        # A frame still waiting belongs to the stream that just ended: show it first.
        self._present()
        self._streaming = False
        self._paused = False
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(False)
        self._set_status(summary)

    def _applied(self, cfg: Config) -> None:
        # What the session really runs on: after a model that would not load or a
        # class the model does not know, the old values -- the panel shows them too.
        self._cfg = cfg
        self._applies_pending = max(0, self._applies_pending - 1)
        if self._applies_pending == 0:
            self._sent = cfg  # answered in full: a reverted value is the one in force
        self.settings.set_config(cfg)
        self.table.setColumnHidden(_COLOUR_COLUMN, not cfg.display.color)

    # --- drawing ----------------------------------------------------------------------

    def _fill_table(self, drawn: list[Detection], target_id: int | None) -> None:
        self.table.setRowCount(len(drawn))
        for row, detection in enumerate(drawn):
            is_target = target_id is not None and detection.track_id == target_id
            track = "" if detection.track_id is None else f"#{detection.track_id}"
            if is_target:
                track = f"{track} {TARGET_MARK}"
            values = (
                track,
                detection.cls_name,
                f"{detection.conf:.2f}",
                f"{detection.dx:+d}" if detection.dx else "0",
                f"{detection.dy:+d}" if detection.dy else "0",
                f"{detection.dx_pct * 100:+.1f}",
                f"{detection.dy_pct * 100:+.1f}",
                detection.color or "",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if is_target:
                    item.setBackground(_TARGET_BRUSH)
                    item.setForeground(_TARGET_TEXT)
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, col, item)
        self.objects.setCurrentWidget(self.table if drawn else self.no_objects_label)

    @staticmethod
    def _status_text(payload: FramePayload) -> str:
        name = payload.source if payload.source.startswith(CAMERA_PREFIX) \
            else Path(payload.source).name
        position = f"frame {payload.index + 1}"
        if payload.total:
            position += f" / {payload.total}"
        parts = [name, position]
        if payload.is_stream:
            parts.append(f"{payload.fps:.1f} FPS")
        parts.append(f"{payload.near_miss_count} near-miss")
        return "  |  ".join(parts)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _notice(self, text: str) -> None:
        self.notice_label.setText(text)
        self._notice_timer.start()

    def _set_open_enabled(self, enabled: bool) -> None:
        for button in (self.open_file_button, self.open_folder_button, self.open_camera_button):
            button.setEnabled(enabled)
        self.camera_box.setEnabled(enabled)

    def _warn(self, sentence: str) -> None:
        QMessageBox.warning(self, WINDOW_TITLE, sentence)

    # --- closing ----------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 -- Qt's name
        """Stop the worker and wait for its thread: the camera is free once we are gone."""
        if self.worker_thread.isRunning():
            self._shutdown.emit()
            # A model still loading or a slow handler can hold the thread for seconds;
            # gone from the screen at once, the window does not look frozen meanwhile.
            self.hide()
            self.worker_thread.wait()
        super().closeEvent(event)
