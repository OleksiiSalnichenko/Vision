"""Compare models on the val frames of a build: accuracy per new class, and speed.

    venv\\Scripts\\python training\\evaluate.py --weights models/yolo26n.pt models/pen.pt --build first
    venv\\Scripts\\python training\\evaluate.py --weights models/pen.pt models/pen-s.pt --build first --imgsz 960

For every model: `YOLO.val` on the CPU over `data/training/build/<name>/images/val`
gives mAP50 and mAP50-95 for each class of `training.classes` and for all
classes every compared model knows (`all`), and `core.detector.Detector` times
a frame the way the app runs it (`bench.warmup` discarded, `bench.runs` timed,
from `config.yaml`). Models with different class lists (the 2-class rough one,
the 82-class one, the stock 80) are scored on the same boxes: the build's labels
are renamed into each model's own IDs by class name, and a class the model does
not know is left out of its score.

Fully offline. `--imgsz` defaults to `model.imgsz` in `config.yaml`; an OpenVINO
folder was exported at one fixed size and is only measured at that size.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

# First project import: it switches Ultralytics offline before anything loads it.
from core.detector import Detector  # noqa: E402
from core.config import load_config  # noqa: E402
from core.source import IMAGE_EXTENSIONS  # noqa: E402
from core.types import Frame  # noqa: E402
from detect import CONFIG_PATH, EXIT_USAGE, configure_console  # noqa: E402
from training.kaggle.train import no_font_download  # noqa: E402
from training.loading import load_model  # noqa: E402
from training.settings import TRAINING_CONFIG_PATH, load_training  # noqa: E402

BUILD_ROOT = PROJECT_ROOT / "data" / "training" / "build"
VAL = "val"
MISSING = "-"  # a class the model does not know, or no box of it in val


def val_set(build: str | Path, model_names: dict[int, str], work: str | Path) -> Path:
    """Copy the build's val images into `work` with labels in the model's class IDs.

    A box is renamed by class name; a box of a class the model does not know is
    dropped (the image stays, so its other boxes still count). Returns the
    `data.yaml` to hand to `YOLO.val`, with an absolute `path`: Ultralytics
    resolves a relative one against the working directory, not the yaml.
    """
    build, work = Path(build), Path(work)
    build_names = _names(build / "data.yaml")
    model_ids = {name: cls_id for cls_id, name in model_names.items()}
    images_dir, labels_dir = work / "images" / VAL, work / "labels" / VAL
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    for image in _val_images(build):
        shutil.copyfile(image, images_dir / image.name)
        label = build / "labels" / VAL / f"{image.stem}.txt"
        lines = []
        text = label.read_text(encoding="utf-8") if label.is_file() else ""
        for number, line in enumerate(text.splitlines(), 1):
            fields = line.split()
            if not fields:
                continue
            name = _box_class(fields, build_names, f"{label}:{number}")
            if name in model_ids:
                lines.append(" ".join([str(model_ids[name]), *fields[1:]]))
        (labels_dir / f"{image.stem}.txt").write_text(
            "".join(f"{line}\n" for line in lines), encoding="utf-8")
    data = work / "data.yaml"
    data.write_text(yaml.safe_dump({
        "path": str(work.resolve()), "train": f"images/{VAL}", "val": f"images/{VAL}",
        "names": dict(model_names),
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return data


def _box_class(fields: list[str], names: list[str], where: str) -> str:
    """The class name of one YOLO box line, or a `ValueError` naming `file:line`."""
    try:
        cls_id = int(fields[0])
        for value in fields[1:]:
            float(value)
    except ValueError:
        cls_id = -1
    if len(fields) != 5 or not 0 <= cls_id < len(names):
        raise ValueError(f"not a YOLO box line of this build: {where}")
    return names[cls_id]


def export_size(weights: str | Path) -> int | None:
    """The fixed `imgsz` an OpenVINO folder was exported at; None for a `.pt` or no metadata."""
    metadata = Path(weights) / "metadata.yaml"
    if not metadata.is_file():
        return None
    size = (yaml.safe_load(metadata.read_text(encoding="utf-8")) or {}).get("imgsz")
    if not size:
        return None
    if not isinstance(size, list):
        return int(size)
    if len(set(size)) != 1:  # one --imgsz is one square: no size of it matches this export
        raise ValueError(f"{weights} was exported at a non-square size "
                         f"{'x'.join(str(side) for side in size)}; evaluate measures square "
                         f"sizes only, export it again at one size")
    return int(size[0])


def _names(data_yaml: Path) -> list[str]:
    if not data_yaml.is_file():
        raise FileNotFoundError(f"not a build folder (no data.yaml): {data_yaml.parent}")
    names = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))["names"]
    return [names[key] for key in sorted(names)] if isinstance(names, dict) else list(names)


def _val_images(build: Path) -> list[Path]:
    folder = build / "images" / VAL
    images = sorted(p for p in folder.glob("*") if p.suffix.lower() in IMAGE_EXTENSIONS) \
        if folder.is_dir() else []
    if not images:
        raise ValueError(f"the build has no val images: {folder}")
    return images


def score(weights: str, build: Path, imgsz: int, work: Path) -> dict[str, tuple[float, float]]:
    """`YOLO.val` of one model: class name -> (mAP50, mAP50-95), for classes with val boxes."""
    from ultralytics import YOLO  # noqa: PLC0415 -- deliberately lazy

    no_font_download()
    model = load_model(lambda: YOLO(weights), weights)
    names = dict(model.names)
    if not set(names.values()) & set(_names(build / "data.yaml")):
        raise ValueError(f"{weights} knows none of the classes of the build {build.name}")
    data = val_set(build, names, work / "data")
    result = model.val(data=str(data), imgsz=imgsz, device="cpu", plots=False, workers=0,
                       verbose=False, project=str(work / "runs"), name=VAL, exist_ok=True)
    box = result.box
    return {names[int(cls_id)]: (float(ap50), float(ap))
            for cls_id, ap50, ap in zip(box.ap_class_index, box.ap50, box.ap)}


def seconds_per_frame(weights: str, images: list[Path], imgsz: int) -> float:
    """Mean `Detector` time per frame: `bench.warmup` frames discarded, `bench.runs` timed."""
    cfg = load_config(CONFIG_PATH)
    cfg = replace(cfg, classes=[], model=replace(cfg.model, weights=weights, imgsz=imgsz))
    detector = load_model(lambda: Detector(cfg), weights)
    frames = [Frame(cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR),
                    str(path), index) for index, path in enumerate(images)]
    for index in range(cfg.bench.warmup):
        detector(frames[index % len(frames)])
    start = time.perf_counter()
    for index in range(cfg.bench.runs):
        detector(frames[index % len(frames)])
    return (time.perf_counter() - start) / cfg.bench.runs


def table(models: list[str], scores: list[dict[str, tuple[float, float]]],
          speeds: list[float], classes: list[str]) -> str:
    """Rows: each class of `classes`, `all` over the classes every model scored, speed."""
    common = sorted(set.intersection(*(set(s) for s in scores)))
    rows = []
    for name in classes:
        for metric, at in (("mAP50", 0), ("mAP50-95", 1)):
            rows.append((f"{name} {metric}",
                         [f"{s[name][at]:.3f}" if name in s else MISSING for s in scores]))
    for metric, at in (("mAP50", 0), ("mAP50-95", 1)):
        rows.append((f"all ({len(common)} classes) {metric}",
                     [f"{np.mean([s[c][at] for c in common]):.3f}" if common else MISSING
                      for s in scores]))
    rows.append(("s/frame", [f"{seconds:.3f}" for seconds in speeds]))
    head = max(len(label) for label, _ in rows)
    width = max(max(len(model) for model in models), 8)
    lines = [" " * head + "".join(f"  {model:>{width}}" for model in models)]
    lines += [f"{label:<{head}}" + "".join(f"  {cell:>{width}}" for cell in cells)
              for label, cells in rows]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare models on the val frames of a build (CPU, offline).")
    parser.add_argument("--weights", nargs="+", required=True,
                        help="models to compare: .pt files or *_openvino_model folders")
    parser.add_argument("--build", required=True,
                        help="build folder name under data/training/build/")
    parser.add_argument("--imgsz", type=int,
                        help="inference size (default: model.imgsz in config.yaml)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)
    try:
        classes = list(load_training(TRAINING_CONFIG_PATH).classes)
        imgsz = args.imgsz or load_config(CONFIG_PATH).model.imgsz
        build = BUILD_ROOT / args.build
        if not build.is_dir():
            raise FileNotFoundError(f"build folder not found: {build}")
        images = _val_images(build)
        for weights in args.weights:
            if not Path(weights).exists():
                raise FileNotFoundError(f"weights not found: {weights}")
            exported = export_size(weights)
            if exported is not None and exported != imgsz:
                raise ValueError(f"{weights} was exported at imgsz {exported}, not {imgsz}; "
                                 f"pass --imgsz {exported} or export it again")
        scores, speeds = [], []
        for weights in args.weights:
            with tempfile.TemporaryDirectory(prefix="vision-eval-") as work:
                scores.append(score(weights, build, imgsz, Path(work)))
            speeds.append(seconds_per_frame(weights, images, imgsz))
    except (OSError, ValueError) as error:  # config, build, weights: one sentence
        print(error, file=sys.stderr)
        return EXIT_USAGE
    print(f"{len(images)} val images of {build}, imgsz {imgsz}, CPU")
    print(table([Path(w).name for w in args.weights], scores, speeds, classes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
