"""Fine-tune the model on the user's build folder, plus a slice of COCO.

The same file runs in two places:

- on Kaggle, pushed by `training/kaggle_run.py train` as a script kernel with no
  arguments: it installs the pinned Ultralytics with pip, finds the user's build
  and COCO under `/kaggle/input`, trains on the GPU and leaves `best.pt` and
  `metrics.json` in `/kaggle/working` for `kaggle_run.py fetch`;
- locally, in the smoke test:

    venv\\Scripts\\python training\\kaggle\\train.py --data-root DIR --out DIR --smoke

  one epoch on the CPU at a tiny image size, which proves the 82-class model
  trains before anything is uploaded.

COCO labels are converted by category *name* into the order of `data.yaml`, so
IDs 0-79 stay the current model's IDs. Nothing is downloaded from Ultralytics:
the base weights come with the build, and `YOLO_OFFLINE` is set before the first
`ultralytics` import. `core/` is not available on Kaggle, so nothing here uses it.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

# Before any ultralytics import, here and in whatever this process loads later:
# no font, AMP-check or weights download, no telemetry, no pip from Ultralytics.
os.environ["YOLO_OFFLINE"] = "1"
os.environ["YOLO_AUTOINSTALL"] = "0"

import yaml  # noqa: E402

ULTRALYTICS_PIN = "ultralytics==8.4.157"  # the version the project runs locally
KAGGLE_INPUT = Path("/kaggle/input")
KAGGLE_WORKING = Path("/kaggle/working")
COCO_SPLITS = ("train", "val")
SEARCH_DEPTH = 4  # how deep under /kaggle/input a mounted dataset may sit
SMOKE_IMGSZ = 64  # 32 gives BatchNorm one value per channel on a last batch of 1
SMOKE_BATCH = 2
LABEL_FORMAT = "{} {:.6f} {:.6f} {:.6f} {:.6f}"
EXIT_USAGE = 2

# `kaggle_run.py train` replaces this line with the text of training/settings.py:
# a script kernel is one file, and the strict loader has to travel with it.
_SETTINGS_SOURCE: str | None = None


def settings_module() -> types.ModuleType:
    """`training.settings`: the project's copy locally, the embedded one on Kaggle."""
    if _SETTINGS_SOURCE is None:
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from training import settings  # noqa: PLC0415

        return settings
    module = types.ModuleType("training_settings")
    sys.modules[module.__name__] = module  # dataclasses look their module up
    module.__file__ = __file__  # its default config path; train() always passes its own
    exec(compile(_SETTINGS_SOURCE, "training/settings.py", "exec"), module.__dict__)  # noqa: S102
    return module


def coco_labels(instances: dict, names: list[str], count: int, seed: int) -> dict[str, list[str]]:
    """YOLO label lines for `count` random images of a COCO `instances_*.json`.

    Class IDs are the positions of the COCO category *names* in `names`; a
    category missing from `names` raises `ValueError`. Crowd and empty boxes are
    skipped; an image without boxes keeps an empty list (a negative).
    """
    unknown = sorted(c["name"] for c in instances["categories"] if c["name"] not in names)
    if unknown:
        raise ValueError(f"COCO categories missing from data.yaml names: {', '.join(unknown)}")
    class_of = {c["id"]: names.index(c["name"]) for c in instances["categories"]}

    images = sorted(instances["images"], key=lambda image: image["id"])
    chosen = random.Random(seed).sample(images, min(count, len(images)))
    by_id = {image["id"]: image for image in chosen}
    labels: dict[str, list[str]] = {image["file_name"]: [] for image in chosen}
    for ann in instances["annotations"]:
        image = by_id.get(ann["image_id"])
        x, y, w, h = ann["bbox"]
        if image is None or ann.get("iscrowd") or w <= 0 or h <= 0:
            continue
        width, height = image["width"], image["height"]
        labels[image["file_name"]].append(LABEL_FORMAT.format(
            class_of[ann["category_id"]],
            (x + w / 2) / width, (y + h / 2) / height, w / width, h / height))
    return labels


def write_coco(coco_root: Path, split: str, names: list[str], count: int, seed: int,
               work: Path) -> Path:
    """Copy `count` COCO `<split>2017` images and their labels under `work`; return the images dir."""
    instances = json.loads(
        (coco_root / "annotations" / f"instances_{split}2017.json").read_text(encoding="utf-8"))
    labels = coco_labels(instances, names, count, seed)
    images_dir = work / "coco" / "images" / split
    labels_dir = work / "coco" / "labels" / split
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    for file_name, lines in labels.items():
        shutil.copy2(coco_root / f"{split}2017" / file_name, images_dir / file_name)
        text = "\n".join(lines) + "\n" if lines else ""
        (labels_dir / file_name).with_suffix(".txt").write_text(text, encoding="utf-8")
    return images_dir


def find_dir(root: Path, marker: str) -> Path | None:
    """The first folder under `root` (at most `SEARCH_DEPTH` deep) holding `marker`."""
    for depth in range(SEARCH_DEPTH + 1):
        found = sorted(root.glob("/".join(["*"] * depth + [marker])))
        if found:
            return found[0].parents[len(Path(marker).parts) - 1]
    return None


def _data_yaml(path: Path, work: Path, train: list[Path], val: Path, names: list[str]) -> Path:
    path.write_text(yaml.safe_dump({
        "path": str(work),
        "train": [str(p) for p in train],
        "val": str(val),
        "names": dict(enumerate(names)),
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _map50(model, data: Path, imgsz: int, batch: int, device) -> tuple[float, dict[int, float]]:
    """mAP50 overall and per class index present in the labels."""
    result = model.val(data=str(data), imgsz=imgsz, batch=batch, device=device, plots=False,
                       workers=0, verbose=False)
    box = result.box
    per_class = {int(c): float(ap) for c, ap in zip(box.ap_class_index, box.ap50)}
    return float(box.map50), per_class


def train(data_root: Path, out: Path, coco_root: Path | None, smoke: bool) -> dict:
    """Train on the build in `data_root`; write `out/best.pt` and `out/metrics.json`."""
    settings = settings_module()
    cfg = settings.load_training(data_root / "training.yaml")
    manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    mode = manifest["mode"]
    raw_names = yaml.safe_load((data_root / "data.yaml").read_text(encoding="utf-8"))["names"]
    names = [raw_names[i] for i in sorted(raw_names)] if isinstance(raw_names, dict) else raw_names
    weights = data_root / Path(cfg.base_weights).name
    if not weights.is_file():
        raise FileNotFoundError(f"base weights not found in the build: {weights.name}")
    if mode == "rough":
        coco_root = None  # the rough model knows only the new classes

    epochs = 1 if smoke else (cfg.rough.epochs if mode == "rough" else cfg.train.epochs)
    imgsz = SMOKE_IMGSZ if smoke else cfg.train.imgsz
    batch = SMOKE_BATCH if smoke else cfg.train.batch
    device = "cpu" if smoke else None

    from ultralytics import YOLO  # noqa: PLC0415 -- after YOLO_OFFLINE is set
    import ultralytics.data.utils  # noqa: PLC0415

    # Every dataset check fetches Arial.ttf from Ultralytics' servers unless it is
    # already cached, YOLO_OFFLINE or not. The font only draws plots, and plots are off.
    ultralytics.data.utils.check_font = lambda *args, **kwargs: None

    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vision-train-") as tmp:
        work = Path(tmp)
        own = work / "own"
        for part in ("images", "labels"):  # Kaggle inputs are read-only; caches go here
            shutil.copytree(data_root / part, own / part)
        train_dirs = [own / "images" / "train"]
        coco_val = None
        if coco_root is not None:
            seed = cfg.dataset.seed
            train_dirs.append(write_coco(coco_root, "train", names, cfg.coco.train_images, seed, work))
            coco_val_dir = write_coco(coco_root, "val", names, cfg.coco.val_images, seed, work)
            coco_val = _data_yaml(work / "coco_val.yaml", work, [coco_val_dir], coco_val_dir, names)
        data = _data_yaml(work / "data.yaml", work, train_dirs, own / "images" / "val", names)

        model = YOLO(str(weights))
        model.train(data=str(data), epochs=epochs, imgsz=imgsz, batch=batch, device=device,
                    workers=0, plots=False, project=str(work / "runs"), name="train",
                    exist_ok=True, verbose=False)
        best = Path(model.trainer.best)
        shutil.copy2(best, out / "best.pt")

        trained = YOLO(str(out / "best.pt"))
        own_val = _data_yaml(work / "own_val.yaml", work, [own / "images" / "val"],
                             own / "images" / "val", names)
        own_map, own_per_class = _map50(trained, own_val, imgsz, batch, device)
        coco = None
        if coco_val is not None:
            base_map, _ = _map50(YOLO(str(weights)), coco_val, imgsz, batch, device)
            trained_map, _ = _map50(trained, coco_val, imgsz, batch, device)
            coco = {"base_mAP50": base_map, "trained_mAP50": trained_map}

    metrics = {
        "mode": mode,
        "epochs": epochs,
        "imgsz": imgsz,
        "names": names,
        "val_own": {"mAP50": own_map,
                    "per_class": {names[c]: ap for c, ap in own_per_class.items()}},
        "coco": coco,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune on a build folder. With no arguments: the Kaggle run.")
    parser.add_argument("--data-root", help="the build folder (default: found under /kaggle/input)")
    parser.add_argument("--coco-root",
                        help="folder holding annotations/ and train2017/, val2017/ (optional)")
    parser.add_argument("--out", help="where best.pt and metrics.json go (default: /kaggle/working)")
    parser.add_argument("--smoke", action="store_true",
                        help="CPU, 1 epoch, tiny image size: proves the run works, learns nothing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    on_kaggle = args.data_root is None
    if on_kaggle:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", ULTRALYTICS_PIN])
        data_root = find_dir(KAGGLE_INPUT, "manifest.json")
        if data_root is None:
            print(f"no build folder (manifest.json) under {KAGGLE_INPUT}", file=sys.stderr)
            return EXIT_USAGE
        coco_root = find_dir(KAGGLE_INPUT, "annotations/instances_train2017.json")
    else:
        data_root = Path(args.data_root)
        coco_root = Path(args.coco_root) if args.coco_root else None
    out = Path(args.out) if args.out else KAGGLE_WORKING

    try:
        mode = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))["mode"]
        if on_kaggle and mode == "full" and coco_root is None:
            print(f"no COCO dataset (annotations/instances_train2017.json) under {KAGGLE_INPUT}",
                  file=sys.stderr)
            return EXIT_USAGE
        metrics = train(data_root, out, coco_root, args.smoke)
    except (OSError, ValueError, KeyError) as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    print(json.dumps(metrics, indent=2))
    print(f"wrote {out / 'best.pt'} and {out / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
