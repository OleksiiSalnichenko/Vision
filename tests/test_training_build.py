"""`training/build_dataset.py`: a Label Studio export becomes one build folder.

The model is a stub that answers by file name, the runtime config, the training
config and the build root all live in `tmp_path`, so nothing under `data/` or
`models/` is touched and no weights are loaded.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from conftest import config_text
from core.geometry import offsets
from core.types import Detection
from test_training_settings import training_text
from training import build_dataset

WIDTH, HEIGHT = 100, 50
CUSTOM = ["stapler", "mug"]  # training.classes in every test config below
BASE = {0: "person", 1: "cell phone", 2: "knife"}  # the stub model's names


def _jpeg(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cv2.imencode(".jpg", np.zeros((HEIGHT, WIDTH, 3), np.uint8))[1].tobytes())
    return path


def make_export(root: Path, labels: dict[str, str | None],
                classes: list[str] | tuple[str, ...] = CUSTOM) -> Path:
    """A Label Studio YOLO export: `labels` maps an image stem to its .txt (None = no file)."""
    (root / "labels").mkdir(parents=True, exist_ok=True)
    (root / "classes.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")
    for stem, text in labels.items():
        _jpeg(root / "images" / f"{stem}.jpg")
        if text is not None:
            (root / "labels" / f"{stem}.txt").write_text(text, encoding="utf-8")
    return root


def det(name: str, conf: float, bbox: tuple[float, float, float, float]) -> Detection:
    cls_id = {v: k for k, v in BASE.items()}.get(name, 99)
    center, dx, dy, dx_pct, dy_pct = offsets(bbox, (WIDTH, HEIGHT))
    return Detection(cls_id, name, conf, bbox, center, dx, dy, dx_pct, dy_pct)


class StubDetector:
    """Stands in for `core.detector.Detector`: boxes chosen by the image's file name."""

    made: list = []
    by_stem: dict[str, list[Detection]] = {}

    def __init__(self, cfg) -> None:
        StubDetector.made.append(cfg)
        self.names = dict(BASE)

    def __call__(self, frame) -> list[Detection]:
        return list(StubDetector.by_stem.get(Path(frame.source).stem, []))


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Training config, runtime config, base weights and build root, all in `tmp_path`."""
    weights = tmp_path / "base.pt"
    weights.write_bytes(b"weights")
    model = tmp_path / "model.pt"
    model.write_bytes(b"model")
    training = tmp_path / "training.yaml"
    training.write_text(training_text({
        "classes": CUSTOM, "base_weights": str(weights),
        "dataset.val_fraction": 0.25, "dataset.pseudo_conf": 0.4,
        "dataset.pseudo_iou_drop": 0.6, "dataset.internet_fraction": 0.2,
        "dataset.min_negative_fraction": 0.3, "dataset.seed": 7,
    }), encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(config_text({"model.weights": str(model), "classes": ["knife"]}),
                      encoding="utf-8")
    monkeypatch.setattr(build_dataset, "TRAINING_CONFIG_PATH", training)
    monkeypatch.setattr(build_dataset, "CONFIG_PATH", config)
    monkeypatch.setattr(build_dataset, "BUILD_ROOT", tmp_path / "build")
    monkeypatch.setattr(build_dataset, "Detector", StubDetector)
    monkeypatch.setattr(StubDetector, "made", [])
    monkeypatch.setattr(StubDetector, "by_stem", {})
    return tmp_path


def one_sentence(err: str) -> bool:
    return err.count("\n") == 1 and "Traceback" not in err


# --- read_ls_export ---------------------------------------------------------

def test_read_export_folder_gives_named_boxes_negatives_and_unlabeled(tmp_path):
    export = make_export(tmp_path / "ls", {
        "desk_000000": "1 0.5 0.5 0.2 0.4\n0 0.1 0.2 0.1 0.1\n",
        "desk_000020": "",
        "desk_000040": None,
    })

    items = {item.image.name: item for item in build_dataset.read_ls_export(export, CUSTOM)}

    assert sorted(items) == ["desk_000000.jpg", "desk_000020.jpg", "desk_000040.jpg"]
    assert items["desk_000000.jpg"].labels == (
        ("mug", 0.5, 0.5, 0.2, 0.4), ("stapler", 0.1, 0.2, 0.1, 0.1))
    assert items["desk_000020.jpg"].labels == ()
    assert items["desk_000040.jpg"].labels is None


def test_read_export_zip_with_a_top_folder(tmp_path):
    export = make_export(tmp_path / "src" / "project-1", {"desk_000000": "0 0.5 0.5 0.2 0.2\n"})
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in export.rglob("*"):
            zf.write(path, path.relative_to(tmp_path / "src").as_posix())

    items = build_dataset.read_ls_export(archive, CUSTOM, tmp_path / "unpacked")

    assert [item.labels for item in items] == [(("stapler", 0.5, 0.5, 0.2, 0.2),)]
    assert items[0].image.is_file()


def test_read_export_refuses_a_class_outside_training_classes(tmp_path):
    export = make_export(tmp_path / "ls", {"a_000000": ""}, classes=["stapler", "knife"])
    with pytest.raises(ValueError, match="knife"):
        build_dataset.read_ls_export(export, CUSTOM)

# --- pseudo_labels ----------------------------------------------------------

def test_pseudo_labels_add_model_boxes_but_not_over_hand_drawn_ones(tmp_path):
    export = make_export(tmp_path / "ls", {"desk_000000": "1 0.5 0.5 0.2 0.4\n", "desk_000020": ""})
    items = build_dataset.read_ls_export(export, CUSTOM)
    # The hand-drawn mug is pixels (40, 15)-(60, 35) in a 100x50 frame.
    StubDetector.by_stem = {"desk_000000": [
        det("knife", 0.9, (40, 15, 60, 35)),    # IoU 1 with the mug: dropped
        det("person", 0.8, (0, 0, 20, 10)),     # kept
        det("knife", 0.7, (45, 15, 65, 35)),    # IoU 0.6 exactly: dropped
        det("knife", 0.6, (50, 15, 70, 35)),    # IoU 1/3: kept
        det("cell phone", 0.3, (80, 0, 100, 10)),  # below pseudo_conf 0.4: dropped
        det("mug", 0.9, (0, 30, 10, 50)),       # a new class from the model: dropped
    ], "desk_000020": [det("person", 0.5, (0, 0, 50, 50))]}

    out = build_dataset.pseudo_labels(items, StubDetector(None), CUSTOM, 0.4, 0.6)

    labelled = {item.image.name: item.labels for item in out}
    assert labelled["desk_000000.jpg"] == (
        ("mug", 0.5, 0.5, 0.2, 0.4),
        ("person", 0.1, 0.1, 0.2, 0.2),
        ("knife", 0.6, 0.5, 0.2, 0.4),
    )
    assert labelled["desk_000020.jpg"] == (("person", 0.25, 0.5, 0.5, 1.0),)

# --- split ------------------------------------------------------------------

def _item(name: str, extra: bool = False) -> build_dataset.Item:
    return build_dataset.Item(Path(name + ".jpg"), (), extra=extra)


def test_split_puts_the_last_block_of_every_video_into_val():
    desk = [f"desk_{index:06d}" for index in range(0, 160, 20)]  # 8 frames
    items = [_item(name) for name in reversed(desk)]
    items += [_item("8f3a2b1c-lamp_000000"), _item("0a1b2c3d-lamp_000020"),
              _item("lamp_000040"), _item("lamp_000060")]  # LS upload prefixes, 4 frames
    items += [_item("room_000000")]  # a video with one frame
    items += [_item(f"web_{index}", extra=True) for index in range(4)]

    train, val = build_dataset.split(items, 0.25, seed=7)

    val_names = sorted(item.image.stem for item in val)
    own_val = [name for name in val_names if not name.startswith("web_")]
    assert own_val == ["desk_000120", "desk_000140", "lamp_000060"]
    assert len([name for name in val_names if name.startswith("web_")]) == 1
    assert len(train) + len(val) == len(items)
    assert any(item.image.stem == "room_000000" for item in train)
    again = build_dataset.split(list(reversed(items)), 0.25, seed=7)
    assert sorted(i.image.stem for i in again[1]) == val_names

# --- extra dataset ------------------------------------------------------------

def make_roboflow(root: Path) -> Path:
    """A Roboflow-style YOLO export: data.yaml with a names list, train/ and valid/."""
    (root).mkdir(parents=True)
    (root / "data.yaml").write_text(yaml.safe_dump({"names": ["Mug", "spoon"]}), encoding="utf-8")
    texts = {"train/a": "0 0.5 0.5 0.1 0.1\n1 0.2 0.2 0.1 0.1\n", "train/b": "1 0.3 0.3 0.1 0.1\n",
             "valid/a": "0 0.4 0.4 0.2 0.2\n", "train/c": ""}
    for name, text in texts.items():
        split_dir, stem = name.split("/")
        _jpeg(root / split_dir / "images" / f"{stem}.jpg")
        (root / split_dir / "labels").mkdir(parents=True, exist_ok=True)
        (root / split_dir / "labels" / f"{stem}.txt").write_text(text, encoding="utf-8")
    return root


def test_read_extra_keeps_images_with_a_wanted_class_and_drops_other_boxes(tmp_path):
    root = make_roboflow(tmp_path / "web")

    items = build_dataset.read_extra(root, CUSTOM)

    assert sorted((item.image.relative_to(root).as_posix(), item.labels) for item in items) == [
        ("train/images/a.jpg", (("mug", 0.5, 0.5, 0.1, 0.1),)),
        ("valid/images/a.jpg", (("mug", 0.4, 0.4, 0.2, 0.2),)),
    ]
    assert all(item.extra for item in items)


def test_read_extra_takes_classes_txt_too(tmp_path):
    export = make_export(tmp_path / "web", {"x": "0 0.5 0.5 0.1 0.1\n"}, classes=["stapler"])
    assert [item.labels for item in build_dataset.read_extra(export, CUSTOM)] == [
        (("stapler", 0.5, 0.5, 0.1, 0.1),)]


def test_pick_extra_is_the_share_of_the_whole_set_and_repeatable():
    pool = [_item(f"web_{index}", extra=True) for index in range(50)]
    picked, short = build_dataset.pick_extra(pool, own=40, fraction=0.2, seed=7)
    assert len(picked) == 10 and not short  # 10 / (40 + 10) = 0.2
    assert picked == build_dataset.pick_extra(list(reversed(pool)), 40, 0.2, 7)[0]

    picked, short = build_dataset.pick_extra(pool[:3], own=40, fraction=0.2, seed=7)
    assert len(picked) == 3 and short

# --- main: the build folder ---------------------------------------------------

def _lines(path: Path) -> list[tuple]:
    return [(int(f[0]), *(round(float(v), 6) for v in f[1:]))
            for f in (line.split() for line in path.read_text(encoding="utf-8").splitlines())]


def desk_export(root: Path) -> Path:
    return make_export(root, {
        "desk_000000": "1 0.5 0.5 0.2 0.4\n",   # mug
        "desk_000020": "0 0.5 0.5 0.1 0.1\n",   # stapler
        "desk_000040": "",                      # negative
        "desk_000060": "0 0.2 0.2 0.1 0.1\n",   # stapler, last quarter -> val
        "desk_000080": None,                    # never labelled: skipped
    })


def test_main_writes_the_build_folder_in_the_shared_format(env, capsys):
    export = desk_export(env / "ls")
    StubDetector.by_stem = {"desk_000040": [det("person", 0.9, (0, 0, 20, 10))]}

    assert build_dataset.main(["--export", str(export), "--name", "first"]) == 0

    out = env / "build" / "first"
    names = ["person", "cell phone", "knife", "stapler", "mug"]
    assert yaml.safe_load((out / "data.yaml").read_text(encoding="utf-8")) == {
        "path": ".", "train": "images/train", "val": "images/val",
        "names": dict(enumerate(names))}
    assert sorted(p.name for p in (out / "images" / "train").iterdir()) == [
        "desk_000000.jpg", "desk_000020.jpg", "desk_000040.jpg"]
    assert [p.name for p in (out / "images" / "val").iterdir()] == ["desk_000060.jpg"]
    assert _lines(out / "labels" / "train" / "desk_000000.txt") == [(4, 0.5, 0.5, 0.2, 0.4)]
    assert _lines(out / "labels" / "train" / "desk_000040.txt") == [(0, 0.1, 0.1, 0.2, 0.2)]
    assert _lines(out / "labels" / "val" / "desk_000060.txt") == [(3, 0.2, 0.2, 0.1, 0.1)]
    assert (out / "training.yaml").read_bytes() == (env / "training.yaml").read_bytes()
    assert (out / "base.pt").read_bytes() == b"weights"

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "first" and manifest["mode"] == "full"
    assert manifest["classes"] == names
    assert manifest["images"] == {"train": 3, "val": 1}
    assert manifest["negatives"] == 1
    assert manifest["sources"] == {"own": 4, "extra": 0}
    assert {k: v for k, v in manifest["counts"]["train"].items() if v} == {
        "person": 1, "stapler": 1, "mug": 1}
    assert {k: v for k, v in manifest["counts"]["val"].items() if v} == {"stapler": 1}

    # The model labelled every class, at pseudo_conf, never the runtime whitelist.
    (cfg,) = StubDetector.made
    assert cfg.classes == [] and cfg.model.conf == 0.4 and cfg.model.conf_debug == 0.4

    captured = capsys.readouterr()
    assert "skipped 1 image with no label file" in captured.out
    assert "3 train, 1 val" in captured.out
    assert "negatives 25%" in captured.out
    assert "warning" in captured.err and "min_negative_fraction" in captured.err


def test_rough_keeps_only_hand_boxes_with_new_class_ids_and_no_model(env):
    export = desk_export(env / "ls")

    assert build_dataset.main(["--export", str(export), "--name", "rough", "--rough"]) == 0

    out = env / "build" / "rough"
    assert StubDetector.made == []
    assert yaml.safe_load((out / "data.yaml").read_text(encoding="utf-8"))["names"] == {
        0: "stapler", 1: "mug"}
    assert _lines(out / "labels" / "train" / "desk_000000.txt") == [(1, 0.5, 0.5, 0.2, 0.4)]
    assert (out / "labels" / "train" / "desk_000040.txt").read_text(encoding="utf-8") == ""
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "rough" and manifest["classes"] == CUSTOM
    assert manifest["images"] == {"train": 3, "val": 1}


def test_rough_with_extra_is_one_sentence(env, capsys):
    export = desk_export(env / "ls")
    code = build_dataset.main(["--export", str(export), "--name", "r", "--rough",
                               "--extra", str(env)])
    err = capsys.readouterr().err
    assert code == 2 and "--extra" in err and one_sentence(err)
    assert not (env / "build").exists()


def test_extra_is_mixed_in_under_its_own_names(env, capsys):
    export = desk_export(env / "ls")  # 4 own frames -> round(4 * 0.2 / 0.8) = 1 extra
    web = make_roboflow(env / "web")

    assert build_dataset.main(["--export", str(export), "--name", "mix", "--extra", str(web)]) == 0

    out = env / "build" / "mix"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sources"] == {"own": 4, "extra": 1}
    extra_files = list(out.glob("labels/*/extra_*.txt"))
    assert len(extra_files) == 1
    assert [line[0] for line in _lines(extra_files[0])] == [4]  # mug; the spoon is gone


def test_an_existing_build_is_refused_without_force_and_emptied_with_it(env, capsys):
    export = desk_export(env / "ls")
    old = env / "build" / "first"
    old.mkdir(parents=True)
    (old / "stale.txt").write_text("old", encoding="utf-8")

    assert build_dataset.main(["--export", str(export), "--name", "first"]) == 2
    err = capsys.readouterr().err
    assert "--force" in err and one_sentence(err)
    assert StubDetector.made == []  # refused before the model loads

    assert build_dataset.main(["--export", str(export), "--name", "first", "--force"]) == 0
    assert not (old / "stale.txt").exists()
    assert (old / "manifest.json").is_file()


@pytest.mark.parametrize("labels, classes, word", [
    ({"a_000000": "0 0.5 0.5 0.1 0.1\n"}, ["stapler", "knife"], "knife"),
    ({"a_000000": "", "a_000020": None}, CUSTOM, "no stapler or mug box"),
])
def test_unknown_class_or_no_new_class_box_is_one_sentence(env, capsys, labels, classes, word):
    export = make_export(env / "ls", labels, classes=classes)
    assert build_dataset.main(["--export", str(export), "--name", "x"]) == 2
    err = capsys.readouterr().err
    assert word in err and one_sentence(err)
    assert not (env / "build").exists()


def test_cyrillic_paths_work(env):
    export = make_export(env / "розмітка", {"стіл_000000": "0 0.5 0.5 0.1 0.1\n",
                                           "стіл_000020": ""})
    StubDetector.by_stem = {"стіл_000020": [det("person", 0.9, (0, 0, 20, 10))]}

    assert build_dataset.main(["--export", str(export), "--name", "ручка"]) == 0

    out = env / "build" / "ручка"
    assert (out / "images" / "train" / "стіл_000000.jpg").is_file()
    # The model read the Cyrillic file: its person box is there.
    assert _lines(out / "labels" / "train" / "стіл_000020.txt") == [(0, 0.1, 0.1, 0.2, 0.2)]
