"""Turn a Label Studio export into one build folder, ready to upload for training.

    venv\\Scripts\\python training\\build_dataset.py --export D:\\ls-export.zip --name first
    venv\\Scripts\\python training\\build_dataset.py --export EXPORT --name first --extra D:\\pens
    venv\\Scripts\\python training\\build_dataset.py --export EXPORT --name rough --rough

Writes `data/training/build/<name>/`: `images/{train,val}`, `labels/{train,val}`
(YOLO lines), `data.yaml`, a copy of `training/training.yaml`, the base weights
and `manifest.json`.

Full mode: the hand-drawn boxes of `training.classes` get the IDs after the
current model's names (`training.classes.class_names`), and the current model
labels its own classes on every frame -- otherwise the people on the frames
would teach the new model that a person is background. A model box that
overlaps a hand-drawn box is dropped, so a pen is never also learnt as a knife.
`--extra` mixes in a ready-made YOLO dataset as `dataset.internet_fraction` of
the whole set.

`--rough`: only the hand-labelled frames and only `training.classes`, IDs
0..k-1, no model labels and no `--extra` -- the small set a quick model is
trained on to pre-label the rest.

Fully offline. Images are read with `np.fromfile` + `cv2.imdecode` and copied
with `shutil`, so paths outside the system code page work.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
import tempfile
import zipfile
from collections.abc import Collection
from dataclasses import dataclass, replace
from pathlib import Path

import cv2
import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

# First project import: it switches Ultralytics offline before anything loads it.
from core.detector import Detector, require_weights  # noqa: E402
from core.config import load_config  # noqa: E402
from core.source import IMAGE_EXTENSIONS  # noqa: E402
from core.types import Frame  # noqa: E402
from detect import CONFIG_PATH, EXIT_USAGE, configure_console  # noqa: E402
from training.classes import class_names  # noqa: E402
from training.extract_frames import FRAMES_ROOT  # noqa: E402
from training.loading import load_model  # noqa: E402
from training.ls_names import disk_frames, frame_name, maybe_dated  # noqa: E402
from training.settings import TRAINING_CONFIG_PATH, load_training  # noqa: E402

BUILD_ROOT = PROJECT_ROOT / "data" / "training" / "build"
MODES = ("full", "rough")

# One YOLO box: class name, then centre x, centre y, width, height, all 0..1.
Label = tuple[str, float, float, float, float]

LS_CLASSES_FILE = "classes.txt"


@dataclass(frozen=True)
class Item:
    """One image of the set. `labels` is None when the image has no label file."""

    image: Path
    labels: tuple[Label, ...] | None
    extra: bool = False  # from the ready-made dataset (--extra), not the user's video


# `<video stem>_<frame index>`, as extract_frames names a frame (after
# `ls_names.frame_name` has taken off Label Studio's prefix).
_FRAME_NAME = re.compile(r"^(?P<video>.+)_(?P<index>\d+)$")


def split(items: list[Item], val_fraction: float, seed: int,
          frames: Collection[str] = ()) -> tuple[list[Item], list[Item]]:
    """Return (train, val) with no frame of one video block leaking into the other.

    Own frames: per video, the last `val_fraction` of its frames by index go to
    val as one block (a video of one frame stays in train). The video is read
    from the exported name through `ls_names.frame_name`, checked against
    `frames`, the names of the frames on disk. Extra images: the same share,
    picked at random with `seed`. Deterministic for the same input.
    """
    videos: dict[str, list[tuple[int, Item]]] = {}
    for item in items:
        if not item.extra:
            name = frame_name(item.image.stem, frames)
            match = _FRAME_NAME.match(name)
            video, index = (match["video"], int(match["index"])) if match else (name, 0)
            videos.setdefault(video, []).append((index, item))
    train, val = [], []
    for video in sorted(videos):
        frames = [item for _, item in sorted(videos[video], key=lambda pair: (
            pair[0], str(pair[1].image)))]
        cut = len(frames) - _val_count(len(frames), val_fraction)
        train += frames[:cut]
        val += frames[cut:]
    extras = sorted((item for item in items if item.extra), key=lambda item: str(item.image))
    random.Random(seed).shuffle(extras)
    count = _val_count(len(extras), val_fraction)
    return train + extras[count:], val + extras[:count]


def _val_count(total: int, fraction: float) -> int:
    return min(round(total * fraction), total - 1) if total else 0


def read_ls_export(path: str | Path, classes: list[str],
                   unpack_dir: str | Path | None = None) -> list[Item]:
    """Read a Label Studio YOLO export (a folder or a zip unpacked into `unpack_dir`).

    Box class IDs are translated into names through the export's `classes.txt`;
    a name outside `classes` is a `ValueError`. An empty label file is a
    negative (no boxes), a missing one leaves `labels` None.
    """
    root = _export_root(Path(path), unpack_dir)
    names = _read_names(root / LS_CLASSES_FILE)
    unknown = [name for name in names if name not in classes]
    if unknown:
        raise ValueError(
            f"the export has classes not in training.classes: {', '.join(unknown)}")
    return [Item(image, _read_labels(_label_path(image, root), names))
            for image in _images(root / "images")]


def read_extra(path: str | Path, classes: list[str]) -> list[Item]:
    """Read a ready-made YOLO dataset (`classes.txt` or `data.yaml` at its top).

    Only images holding a box of `classes` are returned, with every other box
    dropped. Names match without regard to case (Open Images says `Pen`) and
    come back spelt as in `classes`.
    """
    root = Path(path)
    if not root.is_dir():
        raise FileNotFoundError(f"extra dataset not found: {root}")
    if (root / LS_CLASSES_FILE).is_file():
        names = _read_names(root / LS_CLASSES_FILE)
    elif (root / "data.yaml").is_file():
        names = _yaml_names(root / "data.yaml")
    else:
        raise ValueError(f"no {LS_CLASSES_FILE} or data.yaml in the extra dataset: {root}")
    wanted = {name.lower(): name for name in classes}
    items = []
    for image in _images(root):
        labels = tuple((wanted[label[0].lower()], *label[1:])
                       for label in _read_labels(_label_path(image, root), names) or ()
                       if label[0].lower() in wanted)
        if labels:
            items.append(Item(image, labels, extra=True))
    return items


def _yaml_names(path: Path) -> list[str]:
    try:
        names = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("names")
    except yaml.YAMLError:
        raise ValueError(f"not valid YAML: {path}") from None
    if isinstance(names, dict):
        return [str(names[key]) for key in sorted(names)]
    if isinstance(names, list):
        return [str(name) for name in names]
    raise ValueError(f"no names list in {path}")


def pick_extra(pool: list[Item], own: int, fraction: float,
               seed: int) -> tuple[list[Item], bool]:
    """Pick `round(own * f / (1 - f))` of `pool` at random, so they are `f` of the whole set.

    Returns (picked, short); `short` is True when the pool had fewer and all were taken.
    """
    want = round(own * fraction / (1 - fraction))
    pool = sorted(pool, key=lambda item: str(item.image))
    if len(pool) <= want:
        return pool, len(pool) < want
    return random.Random(seed).sample(pool, want), False


def pseudo_labels(items: list[Item], detector, custom: list[str], conf: float,
                  iou_drop: float) -> list[Item]:
    """Add the model's own-class boxes to every item, after its hand-drawn ones.

    Kept: boxes at or above `conf` whose class is not one of `custom` (a model
    already trained on them must not label them for the hand) and whose IoU
    with every hand-drawn box stays below `iou_drop`. No NMS: YOLO26 boxes are
    taken as they come.
    """
    out = []
    for item in items:
        image = _read_image(item.image)
        height, width = image.shape[:2]
        hand = list(item.labels or ())
        added = []
        for detection in detector(Frame(image, str(item.image), 0)):
            if detection.conf < conf or detection.cls_name in custom:
                continue
            x1, y1, x2, y2 = detection.bbox
            box = (detection.cls_name, (x1 + x2) / 2 / width, (y1 + y2) / 2 / height,
                   (x2 - x1) / width, (y2 - y1) / height)
            if all(_iou(box, other) < iou_drop for other in hand):
                added.append(box)
        out.append(replace(item, labels=tuple(hand + added)))
    return out


def _iou(a: Label, b: Label) -> float:
    """IoU of two normalised centre boxes (the same in pixels: both axes scale alike)."""
    ax1, ay1, ax2, ay2 = a[1] - a[3] / 2, a[2] - a[4] / 2, a[1] + a[3] / 2, a[2] + a[4] / 2
    bx1, by1, bx2, by2 = b[1] - b[3] / 2, b[2] - b[4] / 2, b[1] + b[3] / 2, b[2] + b[4] / 2
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = a[3] * a[4] + b[3] * b[4] - inter
    # Rounded: normalised coordinates must not turn an IoU of exactly the
    # threshold into 0.5999999 and keep a box the rule says to drop.
    return round(inter / union, 6) if union > 0 else 0.0


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot read image: {path}")
    return image


def _export_root(path: Path, unpack_dir: str | Path | None) -> Path:
    if path.is_file() and zipfile.is_zipfile(path):
        if unpack_dir is None:
            raise ValueError(f"no folder given to unpack {path} into")
        with zipfile.ZipFile(path) as archive:
            archive.extractall(unpack_dir)
        path = Path(unpack_dir)
    if not path.is_dir():
        raise FileNotFoundError(f"export not found: {path}")
    found = sorted(path.rglob(LS_CLASSES_FILE), key=lambda p: len(p.parts))
    if not found:
        raise ValueError(f"no {LS_CLASSES_FILE} in the export: {path}")
    return found[0].parent


def _read_names(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS)


def _label_path(image: Path, root: Path) -> Path:
    """`.../images/<sub>/x.jpg` -> `.../labels/<sub>/x.txt` (the YOLO convention)."""
    parts = list(image.relative_to(root).parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "images":
            parts[index] = "labels"
            break
    return root.joinpath(*parts).with_suffix(".txt")


def _read_labels(path: Path, names: list[str]) -> tuple[Label, ...] | None:
    if not path.is_file():
        return None
    labels = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split()
        if not fields:
            continue
        try:
            cls_id = int(fields[0])
            cx, cy, w, h = (float(value) for value in fields[1:5])
            name = names[cls_id]
        except (ValueError, IndexError):
            raise ValueError(f"not a YOLO box line: {path}:{number}") from None
        if len(fields) != 5:
            raise ValueError(f"not a YOLO box line: {path}:{number}")
        labels.append((name, cx, cy, w, h))
    return tuple(labels)


def write_build(out_dir: str | Path, train: list[Item], val: list[Item], names: list[str],
                new_classes: list[str], mode: str, training_yaml: str | Path,
                base_weights: str | Path, force: bool = False) -> Path:
    """Write the build folder (format: interfaces.md, "build folder") and return it.

    An existing folder is a `FileExistsError` unless `force`, which empties it
    first: files of an earlier build must never mix into this one. `names`
    gives the IDs; `new_classes` decides which images count as negatives.
    """
    if mode not in MODES:
        raise ValueError(f"unknown build mode: {mode}")
    out_dir = Path(out_dir)
    if out_dir.exists():
        if not force:
            raise FileExistsError(f"{out_dir} already exists; pass --force to replace it")
        shutil.rmtree(out_dir)
    ids = {name: index for index, name in enumerate(names)}
    counts: dict[str, dict[str, int]] = {}
    images = {"train": len(train), "val": len(val)}
    negatives = extra = 0
    for part, items in (("train", train), ("val", val)):
        image_dir = out_dir / "images" / part
        label_dir = out_dir / "labels" / part
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        counts[part] = dict.fromkeys(names, 0)
        for item in items:
            if item.extra:
                extra += 1
                stem = f"extra_{extra:05d}"
            else:
                stem = item.image.stem
            shutil.copyfile(item.image, image_dir / f"{stem}{item.image.suffix.lower()}")
            labels = item.labels or ()
            (label_dir / f"{stem}.txt").write_text("".join(
                f"{ids[name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n"
                for name, cx, cy, w, h in labels), encoding="utf-8")
            for label in labels:
                counts[part][label[0]] += 1
            if not any(label[0] in new_classes for label in labels):
                negatives += 1

    data = {"path": ".", "train": "images/train", "val": "images/val",
            "names": dict(enumerate(names))}
    (out_dir / "data.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    shutil.copyfile(training_yaml, out_dir / "training.yaml")
    shutil.copyfile(base_weights, out_dir / Path(base_weights).name)
    manifest = {
        "name": out_dir.name, "mode": mode, "classes": list(names), "counts": counts,
        "images": images, "negatives": negatives,
        "sources": {"own": len(train) + len(val) - extra, "extra": extra},
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one training folder from a Label Studio YOLO export.")
    parser.add_argument("--export", required=True,
                        help="the Label Studio export: a folder or the downloaded zip")
    parser.add_argument("--name", required=True,
                        help="build folder name under data/training/build/")
    parser.add_argument("--extra", help="a ready-made YOLO dataset to mix in (not with --rough)")
    parser.add_argument("--rough", action="store_true",
                        help="only the hand-labelled frames and only the new classes")
    parser.add_argument("--force", action="store_true",
                        help="empty and rebuild an existing build folder")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)
    try:
        _check_name(args.name)  # before anything is read, written or removed
        with tempfile.TemporaryDirectory(prefix="vision-build-") as scratch:
            return _build(args, Path(scratch))
    except (OSError, ValueError) as error:  # config, export, weights, folder: one sentence
        print(error, file=sys.stderr)
        return EXIT_USAGE


def _check_name(name: str) -> None:
    """`--name` must be one plain folder: `..` or a path would point the rebuild elsewhere."""
    if name in ("", ".", "..") or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError(f"--name must be one plain folder name under {BUILD_ROOT}, "
                         f"not {name!r}")


def _one_each(items: list[Item], frames: Collection[str]) -> None:
    """Refuse one frame exported twice (two folders, or two tasks: `17-x_000020`, `18__x_000020`).

    Checked before the model loads and before anything is written or removed.
    """
    seen: dict[str, Path] = {}
    for item in items:
        name = frame_name(item.image.stem, frames)
        if name in seen:
            raise ValueError(f"the export holds frame {name} twice: {seen[name]} and "
                             f"{item.image}; delete one of the two tasks in Label Studio")
        seen[name] = item.image


def _build(args: argparse.Namespace, scratch: Path) -> int:
    cfg = load_training(TRAINING_CONFIG_PATH)
    custom = list(cfg.classes)
    if args.rough and args.extra:
        raise ValueError("--extra cannot be used with --rough: "
                         "the rough model learns from your own frames only")
    out_dir = BUILD_ROOT / args.name
    if out_dir.exists() and not args.force:
        raise FileExistsError(f"{out_dir} already exists; pass --force to replace it")
    weights = Path(cfg.base_weights)
    weights = weights if weights.is_absolute() else PROJECT_ROOT / weights
    if not weights.is_file():
        raise FileNotFoundError(f"base weights not found (training.base_weights): {weights}")

    items = read_ls_export(args.export, custom, scratch / "export")
    own = [item for item in items if item.labels is not None]
    skipped = len(items) - len(own)
    if skipped:
        print(f"skipped {skipped} image{'s' if skipped != 1 else ''} with no label file")
    frames = disk_frames(FRAMES_ROOT)
    dated = [item.image.stem for item in own if maybe_dated(item.image.stem)]
    if not frames and dated:
        print(f"warning: no frames in {FRAMES_ROOT} to check names against, so "
              f"{dated[0]} is read as frame {frame_name(dated[0])} of video "
              f"{frame_name(dated[0]).rsplit('_', 1)[0]}; clips named with a date "
              f"in front may merge into one", file=sys.stderr)
    _one_each(own, frames)
    if not any(label[0] in custom for item in own for label in item.labels):
        raise ValueError(f"the export has no {' or '.join(custom)} box at all; "
                         f"label some frames in Label Studio first")

    if args.rough:
        names = custom
    else:
        runtime = load_config(CONFIG_PATH)
        conf = cfg.dataset.pseudo_conf
        runtime = replace(runtime, classes=[],
                          model=replace(runtime.model, conf=conf, conf_debug=conf))
        require_weights(runtime)
        detector = load_model(lambda: Detector(runtime), runtime.model.weights)
        names = class_names(detector.names, custom)
        own = pseudo_labels(own, detector, custom, conf, cfg.dataset.pseudo_iou_drop)

    extras: list[Item] = []
    if args.extra:
        fraction = cfg.dataset.internet_fraction
        extras, short = pick_extra(read_extra(args.extra, custom), len(own), fraction,
                                   cfg.dataset.seed)
        if short:
            print(f"warning: the extra dataset has only {len(extras)} images with "
                  f"{' or '.join(custom)}; all are used, below "
                  f"dataset.internet_fraction ({fraction:.0%})", file=sys.stderr)

    train, val = split(own + extras, cfg.dataset.val_fraction, cfg.dataset.seed, frames)
    out = write_build(out_dir, train, val, names, custom, "rough" if args.rough else "full",
                      TRAINING_CONFIG_PATH, weights, force=args.force)
    _print_summary(out, custom, cfg.dataset.min_negative_fraction)
    return 0


def _print_summary(out: Path, custom: list[str], min_negative: float) -> None:
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    images = manifest["images"]
    total = images["train"] + images["val"]
    print(f"wrote {out}: {images['train']} train, {images['val']} val images "
          f"({manifest['sources']['own']} own, {manifest['sources']['extra']} extra)")
    boxes = {name: manifest["counts"]["train"][name] + manifest["counts"]["val"][name]
             for name in manifest["classes"]}
    print("boxes: " + ", ".join(f"{name} {n}" for name, n in boxes.items() if n))
    share = manifest["negatives"] / total
    print(f"negatives {share:.0%} ({manifest['negatives']} of {total} images "
          f"have no {' or '.join(custom)} box)")
    if share < min_negative:
        print(f"warning: negatives are below dataset.min_negative_fraction "
              f"({min_negative:.0%}); add frames of the scene without the objects",
              file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
