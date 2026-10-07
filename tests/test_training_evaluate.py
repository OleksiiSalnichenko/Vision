"""`training/evaluate.py`: models compared on the user's own val frames.

The val set each model is scored on is built by `val_set` without a model: the
build's labels are renamed into the model's own class IDs by name, so a
2-class rough model and the 82-class one are scored on the same boxes. The
rest goes through `main(argv)`; one child process runs a real `YOLO.val` with
the sockets trapped and an empty Ultralytics config dir, so no cached
`Arial.ttf` can hide a font download.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types

import cv2
import numpy as np
import pytest
import yaml

from conftest import PROJECT_ROOT, config_text
from training import evaluate

BASE_WEIGHTS = PROJECT_ROOT / "models" / "yolo26n.pt"


def _write_build(root, names, labels):
    """A build folder (interfaces.md format, val part only): `labels` is stem -> text."""
    (root / "images" / "val").mkdir(parents=True)
    (root / "labels" / "val").mkdir(parents=True)
    for stem, text in labels.items():
        ok, encoded = cv2.imencode(".jpg", np.full((32, 32, 3), 128, dtype=np.uint8))
        assert ok
        (root / "images" / "val" / f"{stem}.jpg").write_bytes(encoded.tobytes())
        (root / "labels" / "val" / f"{stem}.txt").write_text(text, encoding="utf-8")
    (root / "data.yaml").write_text(yaml.safe_dump({
        "path": ".", "train": "images/train", "val": "images/val",
        "names": dict(enumerate(names)),
    }, sort_keys=False), encoding="utf-8")


def test_val_set_renames_classes_into_the_model_ids_and_drops_the_unknown(tmp_path):
    build = tmp_path / "build"
    _write_build(build, ["person", "car", "pen", "flower"], {
        "a": "2 0.5 0.5 0.2 0.2\n0 0.1 0.1 0.1 0.1\n",   # pen, person
        "b": "3 0.4 0.4 0.3 0.3\n1 0.6 0.6 0.2 0.2\n",   # flower, car
        "c": "",                                         # a negative
    })

    data = evaluate.val_set(build, {0: "pen", 1: "flower"}, tmp_path / "work")

    spec = yaml.safe_load(data.read_text(encoding="utf-8"))
    assert spec["names"] == {0: "pen", 1: "flower"}
    root = tmp_path / "work"
    assert sorted(p.name for p in (root / "images" / "val").iterdir()) == ["a.jpg", "b.jpg", "c.jpg"]
    # Worked by hand: pen is 2 in the build and 0 in the model; person and car are unknown.
    labels = root / "labels" / "val"
    assert (labels / "a.txt").read_text(encoding="utf-8").split() == "0 0.5 0.5 0.2 0.2".split()
    assert (labels / "b.txt").read_text(encoding="utf-8").split() == "1 0.4 0.4 0.3 0.3".split()
    assert (labels / "c.txt").read_text(encoding="utf-8") == ""
    # Ultralytics resolves a relative `path` against the working directory, not the yaml.
    assert os.path.isabs(spec["path"])


def test_the_table_scores_all_over_the_classes_every_model_knows():
    rough = {"pen": (0.5, 0.25)}                                       # the 2-class model, no flower box
    full = {"pen": (0.75, 0.5), "person": (0.125, 0.0625)}

    text = evaluate.table(["rough.pt", "full.pt"], [rough, full], [0.05, 0.0625], ["pen", "flower"])

    # Read from the right: the last two columns are the models, the rest is the row label.
    rows = {line.rsplit(None, 2)[0]: line.split()[-2:] for line in text.splitlines()[1:]}
    assert text.splitlines()[0].split() == ["rough.pt", "full.pt"]
    assert rows["pen mAP50"] == ["0.500", "0.750"]
    assert rows["pen mAP50-95"] == ["0.250", "0.500"]
    assert rows["flower mAP50"] == ["-", "-"]
    # `all` is pen alone: person is not known to the rough model.
    assert rows["all (1 classes) mAP50"] == ["0.500", "0.750"]
    assert rows["s/frame"] == ["0.050", "0.062"]


def _box(cx, cy, size=0.2):
    return (cx, cy, size, size)


def test_boxes_are_paired_best_overlap_first_and_each_used_once():
    truths = [(0, _box(0.5, 0.5)), (1, _box(0.8, 0.8))]
    predictions = [(0, _box(0.52, 0.5)), (0, _box(0.9, 0.1)), (1, _box(0.5, 0.5))]

    pairs = evaluate.match_boxes(truths, predictions)

    # Prediction 2 sits exactly on label 0 (IoU 1.0) and wins it over prediction 0 (IoU 0.82).
    assert [(t, p) for t, p, _ in pairs] == [(0, 2)]
    assert pairs[0][2] == pytest.approx(1.0)
    assert evaluate.box_iou(_box(0.5, 0.5), _box(0.6, 0.5)) == pytest.approx(1 / 3)  # worked by hand


def test_tally_counts_true_false_and_missed_boxes_per_class():
    names = {0: "pen", 1: "flower"}
    images = [
        # pen found (IoU 1), flower labelled but guessed as pen, one stray flower guess.
        ([(0, _box(0.2, 0.2)), (1, _box(0.7, 0.7))],
         [(0, _box(0.2, 0.2)), (0, _box(0.7, 0.7)), (1, _box(0.2, 0.8))]),
        # pen labelled and missed.
        ([(0, _box(0.5, 0.5))], []),
    ]

    quality, confusion = evaluate.tally(images, names)

    # pen: TP 1; FP 1 (the flower taken for a pen); FN 1 (the missed one).
    pen = quality["pen"]
    assert (pen.precision, pen.recall, pen.f1) == (0.5, 0.5, 0.5)
    assert pen.iou == pytest.approx(1.0)
    # flower: TP 0; FP 1 (stray); FN 1 (taken for a pen) -> recall 0, precision 0, F1 0, no IoU.
    assert quality["flower"] == evaluate.Quality(precision=0.0, recall=0.0, f1=0.0, iou=None)
    assert confusion == {(0, 0): 1, (1, 0): 1, (None, 1): 1, (0, None): 1}


def test_a_class_without_a_label_gets_no_quality_row_and_no_guess_gives_no_precision():
    names = {0: "pen", 1: "flower", 2: "cup"}
    images = [([(0, _box(0.5, 0.5))], [(2, _box(0.1, 0.1))])]

    quality, _ = evaluate.tally(images, names)

    assert set(quality) == {"pen"}  # cup was guessed, never labelled
    assert quality["pen"].precision is None and quality["pen"].recall == 0.0


def test_the_confusion_png_is_a_png_with_the_background_row():
    from collections import Counter

    data = evaluate.confusion_png(Counter({(0, 0): 3, (0, None): 1, (None, 1): 2}),
                                  {0: "pen", 1: "flower"})

    assert data.startswith(b"\x89PNG")


def test_the_table_adds_quality_rows_when_asked():
    ap = [{"pen": (0.5, 0.25)}]
    good = {"pen": evaluate.Quality(precision=0.75, recall=0.5, f1=0.6, iou=None)}

    text = evaluate.table(["a.pt"], ap, [0.05], ["pen"], [good])

    rows = {line.rsplit(None, 1)[0]: line.split()[-1] for line in text.splitlines()[1:]}
    assert rows["pen P"] == "0.750" and rows["pen R"] == "0.500" and rows["pen F1"] == "0.600"
    assert rows["pen IoU"] == "-"
    assert rows["all (1 classes) P"] == "0.750" and rows["all (1 classes) IoU"] == "-"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """`main` with the build root and training.yaml under `tmp_path`."""
    from test_training_settings import training_text

    training = tmp_path / "training.yaml"
    training.write_text(training_text({"classes": ["pen", "flower"]}), encoding="utf-8")
    monkeypatch.setattr(evaluate, "TRAINING_CONFIG_PATH", training)
    monkeypatch.setattr(evaluate, "BUILD_ROOT", tmp_path / "builds")
    return tmp_path


def test_a_missing_build_is_one_sentence(setup, capsys):
    assert evaluate.main(["--weights", str(BASE_WEIGHTS), "--build", "nope"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("build folder not found:") and "nope" in err
    assert err.count("\n") == 1


def test_missing_weights_are_one_sentence_before_any_model_loads(setup, capsys):
    _write_build(setup / "builds" / "first", ["pen", "flower"], {"a": "0 0.5 0.5 0.2 0.2\n"})

    assert evaluate.main(["--weights", str(setup / "gone.pt"), "--build", "first"]) == 2
    assert capsys.readouterr().err == f"weights not found: {setup / 'gone.pt'}\n"


class FakeYOLO:
    """Stands in for `ultralytics.YOLO`: knows `names`, records every model made."""

    names: dict[int, str] = {}
    made: list = []

    def __init__(self, weights) -> None:
        FakeYOLO.made.append(weights)
        self.names = dict(FakeYOLO.names)

    def val(self, **kwargs):
        raise AssertionError("no test here gets as far as a val")

    def predict(self, image, **kwargs):
        boxes = types.SimpleNamespace(cls=np.zeros(0), xywhn=np.zeros((0, 4)))
        return [types.SimpleNamespace(boxes=boxes)]


@pytest.fixture
def fake_yolo(setup, monkeypatch):
    """`main` with `ultralytics` replaced by `FakeYOLO`; returns a weights file that exists."""
    module = types.ModuleType("ultralytics")
    module.YOLO = FakeYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", module)
    monkeypatch.setattr(evaluate, "no_font_download", lambda: None)
    monkeypatch.setattr(FakeYOLO, "names", {0: "pen", 1: "flower"})
    monkeypatch.setattr(FakeYOLO, "made", [])
    weights = setup / "model.pt"
    weights.write_bytes(b"stub")
    return weights


@pytest.mark.parametrize("bad", ["5 0.5 0.5 0.2 0.2", "0 x 0.5 0.2 0.2", "0 0.5 0.5"])
def test_a_broken_label_line_is_one_sentence_with_file_and_line(setup, fake_yolo, capsys, bad):
    build = setup / "builds" / "first"
    _write_build(build, ["pen", "flower"], {"a": f"0 0.5 0.5 0.2 0.2\n{bad}\n"})

    assert evaluate.main(["--weights", str(fake_yolo), "--build", "first", "--imgsz", "64"]) == 2

    err = capsys.readouterr().err
    assert f"{build / 'labels' / 'val' / 'a.txt'}:2" in err
    assert err.count("\n") == 1 and "Traceback" not in err


def test_a_model_that_knows_none_of_the_build_classes_is_one_sentence(setup, fake_yolo, capsys,
                                                                      monkeypatch):
    monkeypatch.setattr(FakeYOLO, "names", {0: "car", 1: "bus"})
    _write_build(setup / "builds" / "first", ["pen", "flower"], {"a": "0 0.5 0.5 0.2 0.2\n"})

    assert evaluate.main(["--weights", str(fake_yolo), "--build", "first", "--imgsz", "64"]) == 2

    err = capsys.readouterr().err
    assert "knows none of the classes" in err and err.count("\n") == 1


def test_an_openvino_folder_at_another_size_is_one_sentence(setup, fake_yolo, capsys):
    _write_build(setup / "builds" / "first", ["pen", "flower"], {"a": "0 0.5 0.5 0.2 0.2\n"})
    folder = setup / "pen_openvino_model"
    folder.mkdir()
    (folder / "model.xml").write_text("<net/>", encoding="utf-8")
    (folder / "metadata.yaml").write_text(yaml.safe_dump({"imgsz": [320, 320]}),
                                          encoding="utf-8")

    assert evaluate.main(["--weights", str(folder), "--build", "first", "--imgsz", "64"]) == 2

    err = capsys.readouterr().err
    assert str(folder) in err and "320" in err and err.count("\n") == 1
    assert FakeYOLO.made == []  # refused before any model loads


def test_an_openvino_folder_exported_non_square_is_one_sentence(setup, fake_yolo, capsys):
    _write_build(setup / "builds" / "first", ["pen", "flower"], {"a": "0 0.5 0.5 0.2 0.2\n"})
    folder = setup / "pen_openvino_model"
    folder.mkdir()
    (folder / "metadata.yaml").write_text(yaml.safe_dump({"imgsz": [480, 640]}),
                                          encoding="utf-8")

    # 640 is the larger side: a max() of the two would let it through.
    assert evaluate.main(["--weights", str(folder), "--build", "first", "--imgsz", "640"]) == 2

    err = capsys.readouterr().err
    assert str(folder) in err and "480x640" in err and err.count("\n") == 1
    assert FakeYOLO.made == []


def _broken(*args, **kwargs):
    raise RuntimeError("PytorchStreamReader failed\nreading zip archive")


def test_weights_that_will_not_load_are_one_sentence(setup, fake_yolo, capsys, monkeypatch):
    monkeypatch.setattr(sys.modules["ultralytics"], "YOLO", _broken)
    _write_build(setup / "builds" / "first", ["pen", "flower"], {"a": "0 0.5 0.5 0.2 0.2\n"})

    assert evaluate.main(["--weights", str(fake_yolo), "--build", "first", "--imgsz", "64"]) == 2

    err = capsys.readouterr().err
    assert str(fake_yolo) in err and "PytorchStreamReader" in err
    assert err.count("\n") == 1 and "Traceback" not in err


def test_a_detector_that_will_not_load_is_one_sentence(setup, fake_yolo, capsys, monkeypatch,
                                                       write_config):
    box = types.SimpleNamespace(ap_class_index=[0], ap50=[0.5], ap=[0.25])
    monkeypatch.setattr(FakeYOLO, "val", lambda self, **kwargs: types.SimpleNamespace(box=box))
    monkeypatch.setattr(evaluate, "Detector", _broken)
    monkeypatch.setattr(evaluate, "CONFIG_PATH", write_config())
    _write_build(setup / "builds" / "first", ["pen", "flower"], {"a": "0 0.5 0.5 0.2 0.2\n"})

    assert evaluate.main(["--weights", str(fake_yolo), "--build", "first", "--imgsz", "64"]) == 2

    err = capsys.readouterr().err
    assert str(fake_yolo) in err and "PytorchStreamReader" in err
    assert err.count("\n") == 1 and "Traceback" not in err


CHILD = r"""
import json, socket, sys, traceback
from pathlib import Path

calls = []


def trap(name, answer):
    def call(*args, **kwargs):
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

project, builds, training, config, weights = sys.argv[1:6]
sys.path.insert(0, project)

from training import evaluate

evaluate.BUILD_ROOT = Path(builds)
evaluate.TRAINING_CONFIG_PATH = Path(training)
evaluate.CONFIG_PATH = Path(config)
code = evaluate.main(["--weights", weights, "--build", "first", "--imgsz", "64"])
print(json.dumps({"calls": calls, "code": code}))
"""


@pytest.mark.skipif(not BASE_WEIGHTS.is_file(), reason="models/yolo26n.pt is missing")
def test_a_real_val_stays_offline_with_no_font_cached(tmp_path):
    from test_training_settings import training_text

    _write_build(tmp_path / "builds" / "first", ["person", "pen"], {
        "a": "0 0.5 0.5 0.4 0.8\n1 0.2 0.2 0.1 0.1\n", "b": "0 0.3 0.5 0.2 0.6\n"})
    training = tmp_path / "training.yaml"
    training.write_text(training_text({"classes": ["pen", "flower"]}), encoding="utf-8")
    config = tmp_path / "config.yaml"
    out = tmp_path / "out"
    config.write_text(config_text({"bench.runs": 2, "bench.warmup": 1,
                                   "output.dir": out.as_posix()}), encoding="utf-8")
    fonts = tmp_path / "ultralytics-config"  # Ultralytics looks for Arial.ttf here: empty
    fonts.mkdir()

    env = dict(os.environ, YOLO_CONFIG_DIR=str(fonts))
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("YOLO_OFFLINE", None)
    done = subprocess.run(
        [sys.executable, "-c", CHILD, str(PROJECT_ROOT), str(tmp_path / "builds"), str(training),
         str(config), str(BASE_WEIGHTS)],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600,
    )
    assert done.returncode == 0, f"child failed:\n{done.stdout[-3000:]}\n{done.stderr[-3000:]}"
    result = json.loads(done.stdout.strip().splitlines()[-1])

    assert result["calls"] == [], f"network reached during val: {result['calls']}"
    assert result["code"] == 0, done.stderr[-2000:]
    assert not list(fonts.rglob("*.ttf"))
    rows = {line.rsplit(None, 1)[0]: line.rsplit(None, 1)[1]
            for line in done.stdout.splitlines()
            if "mAP50" in line or "s/frame" in line or "classes) R" in line}
    assert rows["pen mAP50"] == "-"  # the stock model has no pen
    assert rows["all (1 classes) mAP50"] != "-"  # person: known to the model, boxed in val
    assert float(rows["s/frame"]) > 0
    assert rows["all (1 classes) R"] != "-"  # person is labelled in val (a blank frame: recall 0)
    assert (out / "confusion_yolo26n.png").read_bytes().startswith(b"\x89PNG")
