"""`training/label_studio.py`: install, start and configure Label Studio.

Label Studio is never installed or started here: `subprocess.run` is replaced
by a recorder, and the venv and the Python launcher are pointed into
`tmp_path`. Only the commands and the environment handed over are checked.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from test_training_settings import training_text
from training import label_studio


class Recorder:
    """Stands in for `subprocess.run`: records each call, returns a set exit code."""

    def __init__(self, returncode: int = 0) -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.returncode = returncode

    def __call__(self, command, **kwargs):
        self.calls.append(([str(part) for part in command], kwargs))
        return subprocess.CompletedProcess(command, self.returncode)


@pytest.fixture
def run(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(label_studio.subprocess, "run", recorder)
    return recorder


@pytest.fixture
def venv(tmp_path, monkeypatch):
    path = tmp_path / "venv-labelstudio"
    monkeypatch.setattr(label_studio, "VENV_DIR", path)
    return path


@pytest.fixture
def training_root(tmp_path, monkeypatch):
    path = tmp_path / "data" / "training"
    monkeypatch.setattr(label_studio, "TRAINING_ROOT", path)
    return path


def _one_sentence(err: str) -> bool:
    return err.count("\n") == 1 and "Traceback" not in err


def _install_exe(venv: Path) -> None:
    scripts = venv / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "label-studio.exe").write_bytes(b"")
    (scripts / "python.exe").write_bytes(b"")


# --- config -----------------------------------------------------------------

def test_labeling_config_is_boxes_only_for_the_given_classes():
    root = ET.fromstring(label_studio.labeling_config(["pen", "flower"]))

    assert root.tag == "View"
    assert [child.tag for child in root] == ["Image", "RectangleLabels"]
    image, boxes = root
    assert image.get("value") == "$image"
    assert boxes.get("toName") == image.get("name")
    assert [label.get("value") for label in boxes] == ["pen", "flower"]


def test_labeling_config_escapes_names():
    root = ET.fromstring(label_studio.labeling_config(['a "b" & <c>']))
    assert [label.get("value") for label in root[1]] == ['a "b" & <c>']


def test_config_prints_the_classes_of_training_yaml(tmp_path, monkeypatch, capsys):
    path = tmp_path / "training.yaml"
    path.write_text(training_text({"classes": ["stapler", "mug"]}), encoding="utf-8")
    monkeypatch.setattr(label_studio, "TRAINING_CONFIG_PATH", path)

    assert label_studio.main(["config"]) == 0

    root = ET.fromstring(capsys.readouterr().out)
    assert [label.get("value") for label in root[1]] == ["stapler", "mug"]


def test_config_with_a_broken_training_yaml_is_one_sentence(tmp_path, monkeypatch, capsys):
    path = tmp_path / "training.yaml"
    path.write_text(training_text(without=("classes",)), encoding="utf-8")
    monkeypatch.setattr(label_studio, "TRAINING_CONFIG_PATH", path)

    assert label_studio.main(["config"]) == 2
    err = capsys.readouterr().err
    assert "classes" in err and _one_sentence(err)


# --- setup ------------------------------------------------------------------

def test_setup_creates_the_venv_then_installs_label_studio_into_it(run, venv, monkeypatch):
    monkeypatch.setattr(label_studio.shutil, "which", lambda name: f"C:/fake/{name}.exe")

    assert label_studio.main(["setup"]) == 0

    commands = [command for command, _ in run.calls]
    assert commands == [
        ["C:/fake/py.exe", "-3.11", "-m", "venv", str(venv)],
        [str(venv / "Scripts" / "python.exe"), "-m", "pip", "install", "label-studio"],
    ]


def test_setup_skips_when_label_studio_is_installed(run, venv, monkeypatch, capsys):
    monkeypatch.setattr(label_studio.shutil, "which", lambda name: f"C:/fake/{name}.exe")
    _install_exe(venv)

    assert label_studio.main(["setup"]) == 0
    assert run.calls == []
    assert capsys.readouterr().out.startswith("skip: ")


def test_setup_without_the_py_launcher_is_one_sentence(run, venv, monkeypatch, capsys):
    monkeypatch.setattr(label_studio.shutil, "which", lambda name: None)

    assert label_studio.main(["setup"]) == 2
    err = capsys.readouterr().err
    assert "py" in err and _one_sentence(err)
    assert run.calls == []


def test_setup_stops_at_a_failed_step(run, venv, monkeypatch, capsys):
    monkeypatch.setattr(label_studio.shutil, "which", lambda name: f"C:/fake/{name}.exe")
    run.returncode = 3

    assert label_studio.main(["setup"]) == 1
    assert len(run.calls) == 1
    assert _one_sentence(capsys.readouterr().err)


# --- start ------------------------------------------------------------------

def test_start_without_the_venv_says_to_run_setup(run, venv, training_root, capsys):
    assert label_studio.main(["start"]) == 2
    err = capsys.readouterr().err
    assert "run training/label_studio.py setup first" in err and _one_sentence(err)
    assert run.calls == []


def test_start_serves_local_files_on_localhost_without_analytics(
        run, venv, training_root, monkeypatch):
    _install_exe(venv)
    monkeypatch.setenv("SOME_USER_VAR", "kept")

    assert label_studio.main(["start"]) == 0

    [(command, kwargs)] = run.calls
    assert command[:2] == [str(venv / "Scripts" / "label-studio.exe"), "start"]
    assert command[2:] == ["--internal-host", "127.0.0.1"]
    env = kwargs["env"]
    assert env["LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED"] == "true"
    assert env["LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT"] == str(training_root.resolve())
    assert env["LABEL_STUDIO_COLLECT_ANALYTICS"] == "false"
    assert env["LABEL_STUDIO_LATEST_VERSION_CHECK"] == "false"
    assert env["SOME_USER_VAR"] == "kept"
