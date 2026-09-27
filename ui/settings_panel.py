"""The settings panel: model, `imgsz`, classes, colour, centre line, save.

Every change is applied at once: the panel emits `changed(Config)` with a new
session config built through `dataclasses.replace` (the loaded one is never
mutated). It knows nothing about the worker or the window; the window wires
`changed` and `save_requested` to them.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.detector import OPENVINO_SUFFIX

_PT_SUFFIX = ".pt"

# YOLO strides are 32 pixels; the input size is a multiple of that. The bounds
# only keep the spin box usable -- the value itself lives in config.yaml.
_IMGSZ_STEP = 32
_IMGSZ_MAX = 4096
_IMGSZ_FIXED_TIP = "fixed by the export — re-run scripts/export_openvino.py --force"


def is_openvino(weights: str) -> bool:
    """True when `weights` names an OpenVINO export folder."""
    return Path(weights).name.endswith(OPENVINO_SUFFIX)


def model_entry(models_dir: str | Path, weights: str) -> str:
    """`weights` in the one spelling the model list uses.

    `./models/a.pt`, `models\\a.pt` and an absolute path inside `models_dir`
    all become `models/a.pt`: relative to the folder that holds `models_dir`,
    forward slashes. A path elsewhere keeps its own, normalised, spelling.
    """
    models_dir = Path(models_dir)
    path = Path(os.path.normpath(weights.replace("\\", "/")))
    if path.is_absolute():
        try:
            inside = path.resolve().relative_to(models_dir.resolve())
        except ValueError:
            return path.as_posix()
        return (Path(models_dir.name) / inside).as_posix()
    return path.as_posix()


def model_choices(models_dir: str | Path, current: str) -> list[str]:
    """`*.pt` files and `*_openvino_model` folders in `models_dir`, plus `current`.

    Each entry is a path the way `config.yaml` writes it: relative to the
    folder that holds `models_dir`, with forward slashes. `current` is kept
    even when it is not on disk, so the list always shows what is in use,
    and appears once however the config spells it.
    """
    models_dir = Path(models_dir)
    found: list[str] = []
    if models_dir.is_dir():
        for entry in sorted(models_dir.iterdir(), key=lambda p: p.name.lower()):
            is_pt = entry.is_file() and entry.suffix.lower() == _PT_SUFFIX
            is_export = entry.is_dir() and entry.name.endswith(OPENVINO_SUFFIX)
            if is_pt or is_export:
                found.append(f"{models_dir.name}/{entry.name}")
    current = model_entry(models_dir, current)
    if current not in found:
        found.insert(0, current)
    return found


class SettingsPanel(QWidget):
    """Session settings; each change emits `changed` with the new `Config`."""

    changed = Signal(object)
    save_requested = Signal()

    def __init__(self, cfg: Config, models_dir: str | Path, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = cfg
        self._models_dir = Path(models_dir)

        self.model_box = QComboBox()
        self.imgsz_box = QSpinBox()
        self.imgsz_box.setRange(_IMGSZ_STEP, _IMGSZ_MAX)
        self.imgsz_box.setSingleStep(_IMGSZ_STEP)

        form = QFormLayout()
        form.addRow("Model", self.model_box)
        form.addRow("imgsz", self.imgsz_box)

        self._class_names: list[str] = []  # the model's, once it has loaded
        self.classes_list = QListWidget()
        self.all_classes_label = QLabel("All classes")

        self.color_check = QCheckBox("Colour")
        self.center_line_check = QCheckBox("Centre line")

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Classes"))
        layout.addWidget(self.classes_list)
        layout.addWidget(self.all_classes_label)
        layout.addWidget(self.color_check)
        layout.addWidget(self.center_line_check)

        self.save_button = QPushButton("Save to config.yaml")
        self.save_button.clicked.connect(self.save_requested)
        layout.addWidget(self.save_button)
        layout.addStretch(1)

        self.set_config(cfg)
        self.classes_list.itemChanged.connect(self._classes_checked)
        self.model_box.currentIndexChanged.connect(self._model_chosen)
        self.imgsz_box.editingFinished.connect(self._imgsz_finished)
        self.color_check.toggled.connect(lambda on: self._display_flag("color", on))
        self.center_line_check.toggled.connect(lambda on: self._display_flag("center_line", on))

    def set_class_names(self, names: dict[int, str]) -> None:
        """Fill the class list from the model's `names`, checked by the whitelist."""
        self._class_names = [names[cls_id] for cls_id in sorted(names)]
        self._fill_classes()

    def config(self) -> Config:
        """The session config the panel currently shows."""
        return self._cfg

    def set_config(self, cfg: Config) -> None:
        """Put every widget back to `cfg` without emitting `changed`."""
        self._cfg = cfg
        self._start_imgsz = cfg.model.imgsz  # what an OpenVINO choice falls back to
        self.model_box.blockSignals(True)
        self.model_box.clear()
        self.model_box.addItems(model_choices(self._models_dir, cfg.model.weights))
        self.model_box.setCurrentText(model_entry(self._models_dir, cfg.model.weights))
        self.model_box.blockSignals(False)
        self.imgsz_box.blockSignals(True)
        self.imgsz_box.setValue(cfg.model.imgsz)
        self.imgsz_box.blockSignals(False)
        self._sync_imgsz_enabled()
        self._fill_classes()
        for check, on in (
            (self.color_check, cfg.display.color),
            (self.center_line_check, cfg.display.center_line),
        ):
            check.blockSignals(True)
            check.setChecked(on)
            check.blockSignals(False)

    def _sync_imgsz_enabled(self) -> None:
        # An OpenVINO export is static: its input size was fixed when it was made.
        exported = is_openvino(self._cfg.model.weights)
        self.imgsz_box.setEnabled(not exported)
        self.imgsz_box.setToolTip(_IMGSZ_FIXED_TIP if exported else "")

    def _emit(self, cfg: Config) -> None:
        self._cfg = cfg
        self.changed.emit(cfg)

    def _model_chosen(self, _index: int) -> None:
        weights = self.model_box.currentText()
        current = model_entry(self._models_dir, self._cfg.model.weights)
        if weights and weights != current:
            model = replace(self._cfg.model, weights=weights)
            if is_openvino(weights):
                # The export's size is fixed; an edited imgsz would be a value the
                # user can neither see take effect nor change while it is chosen.
                model = replace(model, imgsz=self._start_imgsz)
                self.imgsz_box.blockSignals(True)
                self.imgsz_box.setValue(self._start_imgsz)
                self.imgsz_box.blockSignals(False)
            self._emit(replace(self._cfg, model=model))
        self._sync_imgsz_enabled()

    def _imgsz_finished(self) -> None:
        imgsz = self.imgsz_box.value()
        if imgsz != self._cfg.model.imgsz:
            self._emit(replace(self._cfg, model=replace(self._cfg.model, imgsz=imgsz)))

    def _display_flag(self, name: str, on: bool) -> None:
        if getattr(self._cfg.display, name) != on:
            display = replace(self._cfg.display, **{name: on})
            self._emit(replace(self._cfg, display=display))

    def _fill_classes(self) -> None:
        # Whitelisted names the model lacks stay listed: dropping them here
        # would silently rewrite the user's whitelist.
        whitelist = self._cfg.classes
        names = self._class_names + [name for name in whitelist if name not in self._class_names]
        self.classes_list.blockSignals(True)
        self.classes_list.clear()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            on = name in whitelist
            item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            self.classes_list.addItem(item)
        self.classes_list.blockSignals(False)
        self.all_classes_label.setVisible(not whitelist)

    def _checked_classes(self) -> list[str]:
        items = (self.classes_list.item(i) for i in range(self.classes_list.count()))
        return [item.text() for item in items if item.checkState() == Qt.CheckState.Checked]

    def _classes_checked(self, _item: QListWidgetItem) -> None:
        # No check at all means every class, the way an empty list does in config.yaml.
        classes = self._checked_classes()
        self.all_classes_label.setVisible(not classes)
        if classes != self._cfg.classes:
            self._emit(replace(self._cfg, classes=classes))
