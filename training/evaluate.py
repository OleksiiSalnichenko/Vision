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

Next to mAP it reports precision (P), recall (R), F1 and the mean IoU of the
correct boxes, and saves one confusion matrix per model as `<output.dir>/
confusion_<model>.png`. These four are counted at the app's own threshold
(`model.conf`): a prediction and a label that overlap by `MATCH_IOU` are paired,
best overlap first, each used once. A pair of the same class is a true positive;
a pair of two classes is a false positive for the predicted one and a false
negative for the labelled one (and one cell off the diagonal of the matrix); a
prediction with no label is a false positive, a label with no prediction a false
negative. F1 is 2TP / (2TP + FP + FN). A class with no label in val gets no row.

Fully offline. `--imgsz` defaults to `model.imgsz` in `config.yaml`; an OpenVINO
folder was exported at one fixed size and is only measured at that size.
"""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, replace
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
# The "50" of mAP50, a definition and not a knob: a box is found when it covers a label this much.
MATCH_IOU = 0.5
QUALITY_ROWS = (("P", "precision"), ("R", "recall"), ("F1", "f1"), ("IoU", "iou"))
BACKGROUND = "background"

Box = tuple[float, float, float, float]  # normalised centre x, centre y, width, height
Boxes = list[tuple[int, Box]]  # (class id, box)


@dataclass(frozen=True)
class Quality:
    """One class at the app's threshold; None where the denominator is zero."""

    precision: float | None
    recall: float | None
    f1: float | None
    iou: float | None  # mean IoU of the correct boxes


@dataclass(frozen=True)
class Scores:
    ap: dict[str, tuple[float, float]]  # class name -> (mAP50, mAP50-95)
    quality: dict[str, Quality]
    confusion: Counter  # (label class id | None, predicted class id | None) -> boxes
    names: dict[int, str]


def box_iou(a: Box, b: Box) -> float:
    """IoU of two normalised centre boxes (the same in pixels: both axes scale alike)."""
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def match_boxes(truths: Boxes, predictions: Boxes) -> list[tuple[int, int, float]]:
    """Pair labels with predictions, best IoU first, each used once: (label, prediction, IoU)."""
    candidates = sorted(
        ((iou, t, p) for t, (_, truth) in enumerate(truths)
         for p, (_, guess) in enumerate(predictions)
         if (iou := box_iou(truth, guess)) >= MATCH_IOU),
        reverse=True,
    )
    used_t: set[int] = set()
    used_p: set[int] = set()
    pairs = []
    for iou, t, p in candidates:
        if t not in used_t and p not in used_p:
            used_t.add(t)
            used_p.add(p)
            pairs.append((t, p, iou))
    return pairs


def tally(images: list[tuple[Boxes, Boxes]], names: dict[int, str]) -> tuple[dict[str, Quality], Counter]:
    """Per-class `Quality` (classes with a label only) and the confusion counts of all images."""
    tp, fp, fn = Counter(), Counter(), Counter()
    iou_sum: Counter = Counter()
    confusion: Counter = Counter()
    for truths, predictions in images:
        pairs = match_boxes(truths, predictions)
        for t, p, iou in pairs:
            label, guess = truths[t][0], predictions[p][0]
            confusion[(label, guess)] += 1
            if label == guess:
                tp[label] += 1
                iou_sum[label] += iou
            else:
                fn[label] += 1
                fp[guess] += 1
        paired_t = {t for t, _, _ in pairs}
        paired_p = {p for _, p, _ in pairs}
        for t, (label, _) in enumerate(truths):
            if t not in paired_t:
                fn[label] += 1
                confusion[(label, None)] += 1
        for p, (guess, _) in enumerate(predictions):
            if p not in paired_p:
                fp[guess] += 1
                confusion[(None, guess)] += 1

    def ratio(top: float, bottom: float) -> float | None:
        return top / bottom if bottom else None

    quality = {
        names[cls_id]: Quality(
            precision=ratio(tp[cls_id], tp[cls_id] + fp[cls_id]),
            recall=ratio(tp[cls_id], tp[cls_id] + fn[cls_id]),
            f1=ratio(2 * tp[cls_id], 2 * tp[cls_id] + fp[cls_id] + fn[cls_id]),
            iou=ratio(iou_sum[cls_id], tp[cls_id]),
        )
        for cls_id in sorted(names) if tp[cls_id] + fn[cls_id] > 0
    }
    return quality, confusion


def read_truths(label: Path) -> Boxes:
    """The boxes of one YOLO label file, in the class ids it was written with."""
    boxes: Boxes = []
    for line in label.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields:
            boxes.append((int(fields[0]), tuple(float(v) for v in fields[1:5])))
    return boxes


def confusion_png(confusion: Counter, names: dict[int, str]) -> bytes:
    """The confusion matrix as a PNG: labels down, predictions across, plus `background`."""
    import matplotlib  # noqa: PLC0415 -- deliberately lazy; ships with ultralytics

    matplotlib.use("Agg")
    from matplotlib import pyplot  # noqa: PLC0415

    seen = sorted({c for pair in confusion for c in pair if c is not None})
    labels = [names[c] for c in seen] + [BACKGROUND]
    index = {c: i for i, c in enumerate(seen)}
    index[None] = len(seen)
    grid = np.zeros((len(labels), len(labels)), dtype=int)
    for (label, guess), count in confusion.items():
        grid[index[label], index[guess]] = count
    size = max(4.0, 0.6 * len(labels) + 2)
    figure, axes = pyplot.subplots(figsize=(size, size))
    axes.imshow(grid, cmap="Blues")
    axes.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    axes.set_yticks(range(len(labels)), labels)
    axes.set_xlabel("predicted")
    axes.set_ylabel("labelled")
    top = grid.max() or 1
    for (row, col), count in np.ndenumerate(grid):
        if count:
            axes.text(col, row, str(count), ha="center", va="center",
                      color="white" if count > top / 2 else "black")
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=100)
    pyplot.close(figure)
    return buffer.getvalue()


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


def score(weights: str, build: Path, imgsz: int, work: Path, conf: float) -> Scores:
    """One model on the val set: mAP from `YOLO.val`, P/R/F1/IoU and the confusion at `conf`.

    Only classes with val boxes get a row.
    """
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
    ap = {names[int(cls_id)]: (float(ap50), float(ap))
          for cls_id, ap50, ap in zip(box.ap_class_index, box.ap50, box.ap)}

    images = []
    for image in sorted((work / "data" / "images" / VAL).iterdir()):
        truths = read_truths(work / "data" / "labels" / VAL / f"{image.stem}.txt")
        found = model.predict(str(image), imgsz=imgsz, conf=conf, device="cpu", verbose=False)[0]
        guesses = [(int(cls_id), tuple(float(v) for v in xywhn))
                   for cls_id, xywhn in zip(found.boxes.cls.tolist(), found.boxes.xywhn.tolist())]
        images.append((truths, guesses))
    quality, confusion = tally(images, names)
    return Scores(ap, quality, confusion, names)


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


def _cell(quality: Quality | None, field: str) -> str:
    value = None if quality is None else getattr(quality, field)
    return MISSING if value is None else f"{value:.3f}"


def _mean_cell(values: list[float | None]) -> str:
    known = [v for v in values if v is not None]
    return f"{np.mean(known):.3f}" if known else MISSING


def table(models: list[str], scores: list[dict[str, tuple[float, float]]],
          speeds: list[float], classes: list[str],
          qualities: list[dict[str, Quality]] | None = None) -> str:
    """Rows: each class of `classes`, `all` over the classes every model scored, speed.

    With `qualities` each class also gets P, R, F1 and IoU rows, and so does `all`.
    """
    common = sorted(set.intersection(*(set(s) for s in scores)))
    rows = []
    for name in classes:
        for metric, at in (("mAP50", 0), ("mAP50-95", 1)):
            rows.append((f"{name} {metric}",
                         [f"{s[name][at]:.3f}" if name in s else MISSING for s in scores]))
        for label, field in QUALITY_ROWS if qualities is not None else ():
            rows.append((f"{name} {label}", [_cell(q.get(name), field) for q in qualities]))
    for metric, at in (("mAP50", 0), ("mAP50-95", 1)):
        rows.append((f"all ({len(common)} classes) {metric}",
                     [f"{np.mean([s[c][at] for c in common]):.3f}" if common else MISSING
                      for s in scores]))
    if qualities is not None:
        shared = sorted(set.intersection(*(set(q) for q in qualities)))
        for label, field in QUALITY_ROWS:
            rows.append((f"all ({len(shared)} classes) {label}",
                         [_mean_cell([getattr(q[c], field) for c in shared]) for q in qualities]))
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
        cfg = load_config(CONFIG_PATH)
        imgsz = args.imgsz or cfg.model.imgsz
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
        scores, speeds, saved = [], [], []
        for weights in args.weights:
            with tempfile.TemporaryDirectory(prefix="vision-eval-") as work:
                scores.append(score(weights, build, imgsz, Path(work), cfg.model.conf))
            speeds.append(seconds_per_frame(weights, images, imgsz))
            if scores[-1].confusion:
                target = Path(cfg.output.dir) / f"confusion_{Path(weights).stem}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(confusion_png(scores[-1].confusion, scores[-1].names))
                saved.append(target)
    except (OSError, ValueError) as error:  # config, build, weights: one sentence
        print(error, file=sys.stderr)
        return EXIT_USAGE
    print(f"{len(images)} val images of {build}, imgsz {imgsz}, CPU")
    print(f"P, R, F1, IoU at conf {cfg.model.conf}, a box is found at IoU >= {MATCH_IOU}")
    print(table([Path(w).name for w in args.weights], [s.ap for s in scores], speeds, classes,
                [s.quality for s in scores]))
    for target in saved:
        print(f"confusion matrix: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
