"""The settings panel, offscreen: the model list, each widget's one signal, save."""

from __future__ import annotations

import os

# Before the first Qt import: never a window on the user's screen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt

from core.config import load_config
from conftest import schema_value
from ui.settings_panel import _IMGSZ_STEP, SettingsPanel


@pytest.fixture
def cfg(write_config):
    return load_config(write_config())


@pytest.fixture
def models_dir(tmp_path):
    folder = tmp_path / "models"
    folder.mkdir()
    (folder / "a.pt").write_bytes(b"weights")
    exported = folder / "b_openvino_model"
    exported.mkdir()
    (exported / "b.xml").write_text("<net/>", encoding="utf-8")
    (folder / "notes.txt").write_text("not a model", encoding="utf-8")
    return folder


@pytest.fixture
def panel(qtbot, cfg, models_dir):
    widget = SettingsPanel(cfg, models_dir)
    qtbot.addWidget(widget)
    return widget


def model_entries(panel):
    return [panel.model_box.itemText(i) for i in range(panel.model_box.count())]


def test_model_list_holds_pt_openvino_and_the_missing_current(panel):
    entries = model_entries(panel)
    assert "models/a.pt" in entries
    assert "models/b_openvino_model" in entries
    assert "notes.txt" not in " ".join(entries)
    # The current weights (models/yolo26s.pt in the schema) is not on disk, yet shown.
    assert schema_value("model.weights") in entries
    assert panel.model_box.currentText() == schema_value("model.weights")


def emitted(panel, action):
    """Run `action` and return every `changed` payload it produced."""
    seen = []
    panel.changed.connect(seen.append)
    action()
    return seen


def test_choosing_a_model_emits_one_config_with_only_the_weights_changed(qtbot, panel, cfg):
    seen = emitted(panel, lambda: panel.model_box.setCurrentText("models/a.pt"))
    assert len(seen) == 1
    new = seen[0]
    assert new.model.weights == "models/a.pt"
    assert new.model.imgsz == cfg.model.imgsz
    assert new.classes == cfg.classes
    assert new.display == cfg.display
    assert cfg.model.weights == schema_value("model.weights")  # the loaded one is untouched


def test_imgsz_applies_on_editing_finished_with_only_imgsz_changed(qtbot, panel, cfg):
    wanted = schema_value("model.imgsz") + _IMGSZ_STEP

    def edit():
        panel.imgsz_box.setValue(wanted)
        panel.imgsz_box.editingFinished.emit()

    seen = emitted(panel, edit)
    assert len(seen) == 1
    assert seen[0].model.imgsz == wanted
    assert seen[0].model.weights == cfg.model.weights
    assert seen[0].display == cfg.display
    assert seen[0].classes == cfg.classes
    assert panel.imgsz_box.singleStep() == _IMGSZ_STEP


def test_imgsz_is_disabled_for_openvino_and_enabled_for_pt(panel):
    assert panel.imgsz_box.isEnabled()  # the schema's weights are a .pt

    panel.model_box.setCurrentText("models/b_openvino_model")
    assert not panel.imgsz_box.isEnabled()
    assert "scripts/export_openvino.py --force" in panel.imgsz_box.toolTip()

    panel.model_box.setCurrentText("models/a.pt")
    assert panel.imgsz_box.isEnabled()


def test_imgsz_is_disabled_when_the_loaded_config_is_openvino(qtbot, write_config, models_dir):
    cfg = load_config(write_config({"model.weights": "models/b_openvino_model"}))
    widget = SettingsPanel(cfg, models_dir)
    qtbot.addWidget(widget)
    assert not widget.imgsz_box.isEnabled()


@pytest.mark.parametrize(
    ("widget", "key"),
    [("color_check", "color"), ("center_line_check", "center_line")],
)
def test_display_checkbox_emits_one_config_with_only_that_flag_flipped(qtbot, panel, cfg, widget, key):
    before = schema_value(f"display.{key}")
    check = getattr(panel, widget)
    assert check.isChecked() == before

    seen = emitted(panel, check.toggle)
    assert len(seen) == 1
    new = seen[0]
    assert getattr(new.display, key) is (not before)
    others = {name for name in vars(cfg.display) if name != key}
    assert all(getattr(new.display, name) == getattr(cfg.display, name) for name in others)
    assert new.model == cfg.model
    assert new.classes == cfg.classes


MODEL_NAMES = {0: "person", 1: "bicycle", 2: "car", 39: "bottle", 67: "cell phone"}


def class_rows(panel):
    rows = []
    for i in range(panel.classes_list.count()):
        item = panel.classes_list.item(i)
        rows.append((item.text(), item.checkState() == Qt.CheckState.Checked))
    return rows


def checked(panel):
    return [name for name, on in class_rows(panel) if on]


def test_before_the_model_loads_the_list_holds_only_the_whitelist(panel):
    assert class_rows(panel) == [(name, True) for name in schema_value("classes")]


def test_set_class_names_fills_the_list_checked_by_the_whitelist(panel):
    panel.set_class_names(MODEL_NAMES)
    assert [name for name, _ in class_rows(panel)] == list(MODEL_NAMES.values())
    assert sorted(checked(panel)) == sorted(schema_value("classes"))


def test_checking_a_class_emits_one_config_with_only_classes_changed(qtbot, panel, cfg):
    panel.set_class_names(MODEL_NAMES)
    car = panel.classes_list.findItems("car", Qt.MatchFlag.MatchExactly)[0]

    seen = emitted(panel, lambda: car.setCheckState(Qt.CheckState.Checked))
    assert len(seen) == 1
    assert sorted(seen[0].classes) == sorted([*schema_value("classes"), "car"])
    assert seen[0].model == cfg.model
    assert seen[0].display == cfg.display


def test_unchecking_every_class_means_all_classes(qtbot, panel):
    panel.set_class_names(MODEL_NAMES)
    assert panel.all_classes_label.isHidden()

    seen = []
    panel.changed.connect(seen.append)
    for name in schema_value("classes"):
        item = panel.classes_list.findItems(name, Qt.MatchFlag.MatchExactly)[0]
        item.setCheckState(Qt.CheckState.Unchecked)

    assert seen[-1].classes == []
    assert len(seen) == len(schema_value("classes"))
    assert not panel.all_classes_label.isHidden()
    assert panel.all_classes_label.text() == "All classes"


def test_save_button_requests_a_save_and_changes_nothing(qtbot, panel):
    seen = []
    panel.changed.connect(seen.append)
    assert panel.save_button.text() == "Save to config.yaml"
    with qtbot.waitSignal(panel.save_requested, timeout=1000):
        qtbot.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
    assert seen == []


def test_set_config_puts_the_widgets_back_without_a_signal(qtbot, panel, cfg):
    panel.set_class_names(MODEL_NAMES)
    panel.model_box.setCurrentText("models/b_openvino_model")
    panel.color_check.toggle()

    seen = []
    panel.changed.connect(seen.append)
    panel.set_config(cfg)

    assert seen == []
    assert panel.model_box.currentText() == cfg.model.weights
    assert panel.imgsz_box.isEnabled()
    assert panel.color_check.isChecked() == cfg.display.color
    assert sorted(checked(panel)) == sorted(cfg.classes)
    assert len(class_rows(panel)) == len(MODEL_NAMES)  # the model's names are kept


@pytest.mark.parametrize("spelling", ["./models/a.pt", r"models\a.pt", "absolute"])
def test_a_model_on_disk_is_listed_once_however_the_config_spells_it(
    qtbot, write_config, models_dir, spelling
):
    weights = str(models_dir / "a.pt") if spelling == "absolute" else spelling
    cfg = load_config(write_config({"model.weights": weights}))
    widget = SettingsPanel(cfg, models_dir)
    qtbot.addWidget(widget)

    assert model_entries(widget).count("models/a.pt") == 1
    assert len(model_entries(widget)) == 2  # a.pt and b_openvino_model, nothing else
    assert widget.model_box.currentText() == "models/a.pt"

    seen = emitted(widget, lambda: widget.model_box.setCurrentText("models/a.pt"))
    widget.model_box.currentIndexChanged.emit(widget.model_box.currentIndex())
    assert seen == []


def test_switching_to_openvino_restores_the_imgsz_the_session_started_with(panel, cfg):
    edited = cfg.model.imgsz + _IMGSZ_STEP
    panel.imgsz_box.setValue(edited)
    panel.imgsz_box.editingFinished.emit()

    seen = emitted(panel, lambda: panel.model_box.setCurrentText("models/b_openvino_model"))
    assert len(seen) == 1
    assert seen[0].model.weights == "models/b_openvino_model"
    assert seen[0].model.imgsz == schema_value("model.imgsz")
    assert panel.imgsz_box.value() == schema_value("model.imgsz")
    assert not panel.imgsz_box.isEnabled()


def test_a_whitelisted_class_the_model_lacks_stays_listed_and_checked(panel):
    names = {cls_id: name for cls_id, name in MODEL_NAMES.items() if name != "bottle"}
    assert "bottle" in schema_value("classes")

    panel.set_class_names(names)
    assert ("bottle", True) in class_rows(panel)
    assert sorted(checked(panel)) == sorted(schema_value("classes"))


def test_imgsz_emits_nothing_until_editing_finishes(panel):
    seen = emitted(panel, lambda: panel.imgsz_box.setValue(schema_value("model.imgsz") + _IMGSZ_STEP))
    assert seen == []
    panel.imgsz_box.editingFinished.emit()
    assert len(seen) == 1
