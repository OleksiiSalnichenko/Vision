"""`training/kaggle_run.py`: the `kaggle` CLI wrapper, against a fake `kaggle`.

`KAGGLE_EXE` is replaced by a small Python script that appends its arguments to
a log, copies a pushed folder aside and plays the few answers the wrapper needs
(`datasets status`, `kernels output`). The real `kaggle` is never run.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import training.kaggle_run as kaggle_run
from test_training_settings import training_text

FAKE = r"""
import json, os, shutil, sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_KAGGLE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
if args[:2] == ["datasets", "status"]:
    sys.exit(int(os.environ.get("FAKE_STATUS_EXIT", "0")))
if args[:2] == ["kernels", "push"]:
    shutil.copytree(args[args.index("-p") + 1], os.environ["FAKE_KAGGLE_PUSHED"])
if args[:2] == ["kernels", "output"]:
    out = Path(args[args.index("-p") + 1])
    (out / "best.pt").write_bytes(b"fake weights")
    (out / "metrics.json").write_text('{"mode": "full"}', encoding="utf-8")
"""

WEIGHTS_BYTES = b"fake weights"


@pytest.fixture
def kaggle(tmp_path, monkeypatch):
    """A fake `kaggle`, a `training.yaml`, a build folder and an empty models/."""
    fake = tmp_path / "fake_kaggle.py"
    fake.write_text(FAKE, encoding="utf-8")
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_KAGGLE_LOG", str(log))
    monkeypatch.setenv("FAKE_KAGGLE_PUSHED", str(tmp_path / "pushed"))
    monkeypatch.setattr(kaggle_run, "KAGGLE_EXE", [sys.executable, str(fake)])

    key = tmp_path / ".kaggle" / "kaggle.json"
    key.parent.mkdir()
    key.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(kaggle_run, "KAGGLE_JSON", key)

    config = tmp_path / "training.yaml"
    config.write_text(training_text(), encoding="utf-8")
    monkeypatch.setattr(kaggle_run, "TRAINING_CONFIG_PATH", config)

    build = tmp_path / "build" / "first"
    (build / "images").mkdir(parents=True)
    (build / "images" / "a.jpg").write_bytes(b"x" * 2048)
    monkeypatch.setattr(kaggle_run, "BUILD_ROOT", tmp_path / "build")

    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setattr(kaggle_run, "MODELS_DIR", models)

    class Fake:
        root = tmp_path

        def calls(self):
            if not log.is_file():
                return []
            return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    return Fake()


def test_check_says_ok_when_everything_is_in_place(kaggle, capsys):
    assert kaggle_run.main(["check"]) == 0
    assert capsys.readouterr().out.strip() == "ok"


def test_check_names_every_problem_in_one_sentence_each(kaggle, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(kaggle_run, "KAGGLE_EXE", None)
    monkeypatch.setattr(kaggle_run, "KAGGLE_JSON", tmp_path / "nowhere" / "kaggle.json")
    (tmp_path / "training.yaml").write_text(
        training_text({"kaggle.username": ""}), encoding="utf-8")

    assert kaggle_run.main(["check"]) == 2
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 3
    assert "requirements-training.txt" in err[0]
    assert "kaggle.json" in err[1]
    assert err[2] == "set training.kaggle.username in training/training.yaml"


def test_upload_without_yes_only_shows_the_plan(kaggle, capsys):
    assert kaggle_run.main(["upload", "--build", "first"]) == 0
    out = capsys.readouterr().out
    assert "someone/my-data" in out
    assert "private" in out
    assert "MB" in out
    assert "--yes" in out
    assert kaggle.calls() == []


def test_upload_creates_the_dataset_the_first_time(kaggle, monkeypatch):
    monkeypatch.setenv("FAKE_STATUS_EXIT", "1")  # Kaggle does not know the dataset yet
    build = kaggle.root / "build" / "first"

    assert kaggle_run.main(["upload", "--build", "first", "--yes"]) == 0

    assert kaggle.calls() == [
        ["datasets", "status", "someone/my-data"],
        ["datasets", "create", "-p", str(build), "--dir-mode", "zip"],
    ]
    meta = json.loads((build / "dataset-metadata.json").read_text(encoding="utf-8"))
    assert meta["id"] == "someone/my-data"


def test_upload_adds_a_version_when_the_dataset_exists(kaggle):
    build = kaggle.root / "build" / "first"

    assert kaggle_run.main(["upload", "--build", "first", "--yes"]) == 0

    status, version = kaggle.calls()
    assert status == ["datasets", "status", "someone/my-data"]
    assert version[:4] == ["datasets", "version", "-p", str(build)]
    assert version[-2:] == ["--dir-mode", "zip"]
    assert "-m" in version


def test_upload_of_a_missing_build_is_a_usage_error(kaggle, capsys):
    assert kaggle_run.main(["upload", "--build", "nope", "--yes"]) == 2
    assert "nope" in capsys.readouterr().err
    assert kaggle.calls() == []


def test_network_commands_refuse_an_empty_username(kaggle, capsys):
    (kaggle.root / "training.yaml").write_text(
        training_text({"kaggle.username": ""}), encoding="utf-8")

    assert kaggle_run.main(["upload", "--build", "first"]) == 2
    assert capsys.readouterr().err.strip() == (
        "set training.kaggle.username in training/training.yaml")


def test_a_yes_without_the_kaggle_cli_is_a_usage_error(kaggle, monkeypatch, capsys):
    monkeypatch.setattr(kaggle_run, "KAGGLE_EXE", None)

    assert kaggle_run.main(["status", "--yes"]) == 2
    assert "requirements-training.txt" in capsys.readouterr().err


def test_train_without_yes_only_shows_the_plan(kaggle, capsys):
    assert kaggle_run.main(["train"]) == 0
    out = capsys.readouterr().out
    assert "someone/my-kernel" in out
    assert "owner/coco" in out
    assert kaggle.calls() == []


def test_train_pushes_a_private_gpu_script_kernel_with_both_datasets(kaggle):
    assert kaggle_run.main(["train", "--yes"]) == 0

    (call,) = kaggle.calls()
    assert call[:2] == ["kernels", "push"]
    pushed = kaggle.root / "pushed"
    meta = json.loads((pushed / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert meta["id"] == "someone/my-kernel"
    assert meta["kernel_type"] == "script"
    assert meta["language"] == "python"
    assert meta["is_private"] is True
    assert meta["enable_gpu"] is True
    assert meta["enable_internet"] is True
    assert meta["dataset_sources"] == ["someone/my-data", "owner/coco"]
    assert (pushed / meta["code_file"]).is_file()


def test_rough_training_leaves_coco_out(kaggle):
    assert kaggle_run.main(["train", "--rough", "--yes"]) == 0

    meta = json.loads((kaggle.root / "pushed" / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert meta["dataset_sources"] == ["someone/my-data"]


def test_the_pushed_script_carries_the_settings_loader_with_it(kaggle, tmp_path):
    """On Kaggle there is no `training/` package: the loader travels inside the script."""
    assert kaggle_run.main(["train", "--yes"]) == 0
    pushed = tmp_path / "pushed"
    script = pushed / json.loads(
        (pushed / "kernel-metadata.json").read_text(encoding="utf-8"))["code_file"]

    probe = (
        "import runpy, sys\n"
        "module = runpy.run_path(sys.argv[1], run_name='pushed')\n"
        "cfg = module['settings_module']().load_training(sys.argv[2])\n"
        "print(cfg.kaggle.kernel_slug)\n"
    )
    done = subprocess.run(  # -I: the project is not on sys.path, as on Kaggle
        [sys.executable, "-I", "-c", probe, str(script), str(tmp_path / "training.yaml")],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "my-kernel"


def test_status_asks_for_the_kernel(kaggle):
    assert kaggle_run.main(["status", "--yes"]) == 0
    assert kaggle.calls() == [["kernels", "status", "someone/my-kernel"]]


def test_fetch_puts_the_model_into_models_and_says_how_to_use_it(kaggle, capsys):
    assert kaggle_run.main(["fetch", "--name", "pen82", "--yes"]) == 0

    (call,) = kaggle.calls()
    assert call[:3] == ["kernels", "output", "someone/my-kernel"]
    models = kaggle.root / "models"
    assert (models / "pen82.pt").read_bytes() == WEIGHTS_BYTES
    assert json.loads((models / "pen82.metrics.json").read_text(encoding="utf-8")) == {
        "mode": "full"}
    out = capsys.readouterr().out
    assert hashlib.sha256(WEIGHTS_BYTES).hexdigest() in out
    assert "model.weights: models/pen82.pt" in out
    assert "export_openvino.py --weights models/pen82.pt" in out


def test_fetch_does_not_overwrite_a_model_without_force(kaggle, capsys):
    existing = kaggle.root / "models" / "pen82.pt"
    existing.write_bytes(b"old")

    assert kaggle_run.main(["fetch", "--name", "pen82", "--yes"]) == 2
    assert "--force" in capsys.readouterr().err
    assert existing.read_bytes() == b"old"
    assert kaggle.calls() == []

    assert kaggle_run.main(["fetch", "--name", "pen82", "--yes", "--force"]) == 0
    assert existing.read_bytes() == WEIGHTS_BYTES


def test_fetch_without_yes_downloads_nothing(kaggle, capsys):
    assert kaggle_run.main(["fetch", "--name", "pen82"]) == 0
    assert "--yes" in capsys.readouterr().out
    assert kaggle.calls() == []
    assert not Path(kaggle.root / "models" / "pen82.pt").exists()
