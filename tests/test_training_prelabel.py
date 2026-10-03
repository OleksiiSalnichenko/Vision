"""`training/prelabel.py`: a model's boxes as Label Studio pre-annotations.

The model is a stub handed in through `prelabel.Detector`; frames are tiny JPEGs
in `tmp_path`, which also stands in for `data/training` (Label Studio's
document root). No weights are loaded, nothing goes to the network.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from conftest import schema_value
from core.types import Detection, Frame
from test_training_settings import training_text
from training import prelabel


def det(cls_name: str, conf: float, bbox: tuple[float, float, float, float]) -> Detection:
    return Detection(cls_id=0, cls_name=cls_name, conf=conf, bbox=bbox, center=(0, 0),
                     dx=0, dy=0, dx_pct=0.0, dy_pct=0.0)


# --- tasks ------------------------------------------------------------------

def test_tasks_turn_pixel_boxes_into_percent_rectangles(tmp_path):
    root = tmp_path / "training"
    first = root / "frames" / "desk" / "desk_000000.jpg"
    second = root / "frames" / "desk" / "desk_000020.jpg"
    images = {first: (200, 100), second: (640, 480)}
    detections = {
        first: [det("pen", 0.8, (10.0, 20.0, 50.0, 60.0)),
                det("person", 0.9, (0.0, 0.0, 100.0, 100.0))],
        second: [],
    }

    tasks = prelabel.tasks(images, detections, ["pen", "flower"], root)

    assert [task["data"]["image"] for task in tasks] == [
        "/data/local-files/?d=frames/desk/desk_000000.jpg",
        "/data/local-files/?d=frames/desk/desk_000020.jpg",
    ]
    [prediction] = tasks[0]["predictions"]
    [box] = prediction["result"]  # `person` is not a training class
    assert box["type"] == "rectanglelabels"
    assert (box["from_name"], box["to_name"]) == ("label", "image")
    assert (box["original_width"], box["original_height"]) == (200, 100)
    assert box["score"] == pytest.approx(0.8)
    value = box["value"]
    assert value["rectanglelabels"] == ["pen"]
    # 10..50 of 200 px wide, 20..60 of 100 px high, worked out by hand.
    assert value["x"] == pytest.approx(5.0)
    assert value["y"] == pytest.approx(20.0)
    assert value["width"] == pytest.approx(20.0)
    assert value["height"] == pytest.approx(40.0)
    assert tasks[1]["predictions"] == [{"result": []}]
    json.dumps(tasks)  # the import file is plain JSON


# --- main -------------------------------------------------------------------

class StubDetector:
    """Stands in for `Detector`: records its config and each frame's size."""

    made: list = []

    def __init__(self, cfg) -> None:
        StubDetector.made.append(cfg)

    def __call__(self, frame: Frame) -> list[Detection]:
        h, w = frame.image.shape[:2]
        return [det("flower", 0.7, (0.0, 0.0, w / 2, h / 2))]


@pytest.fixture
def setup(tmp_path, monkeypatch, write_config):
    root = tmp_path / "data" / "training"
    frames = root / "frames" / "desk"
    frames.mkdir(parents=True)
    for index in (0, 20, 40):
        ok, data = cv2.imencode(".jpg", np.zeros((50, 80, 3), np.uint8))
        (frames / f"desk_{index:06d}.jpg").write_bytes(data.tobytes())
    weights = tmp_path / "rough.pt"
    weights.write_bytes(b"stub")
    training = tmp_path / "training.yaml"
    training.write_text(training_text({"classes": ["pen", "flower"]}), encoding="utf-8")

    monkeypatch.setattr(prelabel, "TRAINING_ROOT", root)
    monkeypatch.setattr(prelabel, "TRAINING_CONFIG_PATH", training)
    monkeypatch.setattr(prelabel, "CONFIG_PATH", write_config({"classes": ["person"]}))
    monkeypatch.setattr(prelabel, "Detector", StubDetector)
    StubDetector.made = []
    return {"root": root, "frames": frames, "weights": weights, "tmp": tmp_path}


def _run(setup, *extra: str) -> int:
    return prelabel.main(["--weights", str(setup["weights"]), "--frames", str(setup["frames"]),
                          *extra])


def test_main_writes_an_import_file_with_every_frame(setup, capsys):
    assert _run(setup) == 0

    out = setup["root"] / "tasks.json"
    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert [task["data"]["image"].rsplit("/", 1)[1] for task in tasks] == [
        "desk_000000.jpg", "desk_000020.jpg", "desk_000040.jpg"]
    value = tasks[0]["predictions"][0]["result"][0]["value"]
    assert value["rectanglelabels"] == ["flower"]
    assert (value["width"], value["height"]) == (pytest.approx(50.0), pytest.approx(50.0))
    assert f"wrote 3 tasks to {out}" in capsys.readouterr().out


def test_the_model_is_the_given_weights_with_every_class(setup):
    assert _run(setup) == 0

    [cfg] = StubDetector.made
    assert cfg.model.weights == str(setup["weights"])
    assert cfg.classes == []
    assert cfg.model.imgsz == schema_value("model.imgsz")


def test_frames_with_a_label_file_in_the_export_are_skipped(setup):
    export = setup["tmp"] / "export"
    (export / "labels").mkdir(parents=True)
    (export / "labels" / "desk_000000.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    (export / "labels" / "desk_000020.txt").write_text("", encoding="utf-8")  # a negative
    out = setup["tmp"] / "rest.json"

    assert _run(setup, "--skip-labelled", str(export), "--out", str(out)) == 0

    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert [task["data"]["image"].rsplit("/", 1)[1] for task in tasks] == ["desk_000040.jpg"]


def test_the_export_may_be_a_zip(setup):
    export = setup["tmp"] / "export.zip"
    with zipfile.ZipFile(export, "w") as archive:
        archive.writestr("labels/desk_000040.txt", "")
        archive.writestr("classes.txt", "flower\npen\n")

    assert _run(setup, "--skip-labelled", str(export)) == 0

    tasks = json.loads((setup["root"] / "tasks.json").read_text(encoding="utf-8"))
    assert len(tasks) == 2


def _one_sentence(err: str) -> bool:
    return err.count("\n") == 1 and "Traceback" not in err


def test_frames_outside_data_training_are_refused(setup, tmp_path, capsys):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert prelabel.main(["--weights", str(setup["weights"]), "--frames", str(elsewhere)]) == 2
    err = capsys.readouterr().err
    assert str(setup["root"]) in err and _one_sentence(err)
    assert StubDetector.made == []


def test_a_folder_without_frames_is_one_sentence(setup, capsys):
    empty = setup["root"] / "frames" / "empty"
    empty.mkdir()
    assert prelabel.main(["--weights", str(setup["weights"]), "--frames", str(empty)]) == 2
    err = capsys.readouterr().err
    assert "no frames" in err and _one_sentence(err)


def test_missing_weights_are_one_sentence(setup, capsys):
    setup["weights"].unlink()
    assert _run(setup) == 2
    assert _one_sentence(capsys.readouterr().err)
    assert StubDetector.made == []


def test_a_missing_export_is_one_sentence(setup, capsys):
    missing = setup["tmp"] / "nope"
    assert _run(setup, "--skip-labelled", str(missing)) == 2
    err = capsys.readouterr().err
    assert str(missing) in err and _one_sentence(err)
