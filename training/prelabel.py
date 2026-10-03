"""Pre-annotate frames with a model, as a Label Studio import file.

    venv\\Scripts\\python training\\prelabel.py --weights models\\rough.pt
        --frames data\\training\\frames\\desk --skip-labelled data\\training\\exports\\first50.zip

Runs the model (usually the rough two-class one) over every frame that has no
label file in the given Label Studio YOLO export yet, and writes
`data/training/tasks.json`: one task per frame, its image addressed through Label
Studio's local-files URL and the model's boxes as `predictions`. Imported into
the project, the boxes show up ready to correct instead of to draw.

Fully offline. Boxes are taken as the model returns them -- YOLO26 removes its
own duplicates, so there is no NMS here.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

import core.detector  # noqa: E402,F401  -- first: sets the offline switches
import cv2  # noqa: E402
import numpy as np  # noqa: E402

from core.config import ConfigError, load_config  # noqa: E402
from core.detector import Detector, require_weights  # noqa: E402
from core.source import IMAGE_EXTENSIONS  # noqa: E402
from core.types import Detection, Frame  # noqa: E402
from detect import CONFIG_PATH, EXIT_USAGE, configure_console  # noqa: E402
from training.label_studio import IMAGE_NAME, LABEL_NAME  # noqa: E402
from training.settings import (  # noqa: E402
    TRAINING_CONFIG_PATH,
    TrainingConfigError,
    load_training,
)

# Label Studio's document root for local files (`label_studio.py start`).
TRAINING_ROOT = PROJECT_ROOT / "data" / "training"
LOCAL_FILES_URL = "/data/local-files/?d="
TASKS_NAME = "tasks.json"


def tasks(images: dict[Path, tuple[int, int]],
          detections_by_image: dict[Path, list[Detection]],
          classes: list[str],
          image_root: Path) -> list[dict]:
    """One Label Studio task per image, in `images` order, with the boxes as a prediction.

    `images` maps each image (inside `image_root`) to its `(width, height)`;
    boxes are given in pixels and stored in percent of that size, as Label
    Studio expects. Boxes of a class outside `classes` are left out.
    """
    result = []
    for image, (width, height) in images.items():
        boxes = [_rectangle(d, width, height) for d in detections_by_image.get(image, [])
                 if d.cls_name in classes]
        result.append({
            "data": {IMAGE_NAME: LOCAL_FILES_URL + image.relative_to(image_root).as_posix()},
            "predictions": [{"result": boxes}],
        })
    return result


def _rectangle(detection: Detection, width: int, height: int) -> dict:
    x1, y1, x2, y2 = detection.bbox
    return {
        "from_name": LABEL_NAME,
        "to_name": IMAGE_NAME,
        "type": "rectanglelabels",
        "original_width": width,
        "original_height": height,
        "image_rotation": 0,
        "score": detection.conf,
        "value": {
            "x": 100.0 * x1 / width,
            "y": 100.0 * y1 / height,
            "width": 100.0 * (x2 - x1) / width,
            "height": 100.0 * (y2 - y1) / height,
            "rotation": 0,
            "rectanglelabels": [detection.cls_name],
        },
    }


def labelled_stems(export: Path) -> set[str]:
    """Stems of the label files in a Label Studio YOLO export (folder or zip).

    A label file means the frame was annotated, even an empty one (a negative).
    """
    if zipfile.is_zipfile(export):
        with zipfile.ZipFile(export) as archive:
            paths = [PurePosixPath(name) for name in archive.namelist()]
    else:
        paths = [PurePosixPath(path.relative_to(export).as_posix())
                 for path in export.rglob("*.txt")]
    return {path.stem for path in paths if path.suffix == ".txt" and "labels" in path.parts}


def _is_labelled(stem: str, labelled: set[str]) -> bool:
    # Label Studio may prefix an exported file name with an id ("<id>-name", "<id>__name").
    return any(label == stem or label.endswith(("-" + stem, "__" + stem)) for label in labelled)


def _read(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot read image: {path}")
    return image


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a Label Studio import file with a model's boxes as predictions.")
    parser.add_argument("--weights", required=True, help="the model to pre-annotate with")
    parser.add_argument("--frames", required=True,
                        help="folder of frames, inside data/training (searched recursively)")
    parser.add_argument("--out", help=f"the import file (default: data/training/{TASKS_NAME})")
    parser.add_argument("--skip-labelled", metavar="EXPORT",
                        help="a Label Studio YOLO export (folder or zip); its frames are left out")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)
    root = TRAINING_ROOT.resolve()
    frames_dir = Path(args.frames).resolve()
    out = Path(args.out) if args.out else TRAINING_ROOT / TASKS_NAME

    try:
        training = load_training(TRAINING_CONFIG_PATH)
        cfg = load_config(CONFIG_PATH)
    except (TrainingConfigError, ConfigError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    # The given weights, every class they know; only boxes the model is sure of.
    cfg = dataclasses.replace(
        cfg, classes=[],
        model=dataclasses.replace(cfg.model, weights=args.weights, conf_debug=cfg.model.conf))

    if not frames_dir.is_relative_to(root):
        print(f"frames must be inside {TRAINING_ROOT}, the folder Label Studio serves",
              file=sys.stderr)
        return EXIT_USAGE
    frames = sorted(path for path in frames_dir.rglob("*")
                    if path.suffix.lower() in IMAGE_EXTENSIONS)
    if args.skip_labelled:
        export = Path(args.skip_labelled)
        if not export.exists():
            print(f"export not found: {export}", file=sys.stderr)
            return EXIT_USAGE
        labelled = labelled_stems(export)
        frames = [path for path in frames if not _is_labelled(path.stem, labelled)]
    if not frames:
        print(f"no frames to pre-annotate in {frames_dir}", file=sys.stderr)
        return EXIT_USAGE

    try:
        require_weights(cfg)
        detector = Detector(cfg)
        sizes: dict[Path, tuple[int, int]] = {}
        found: dict[Path, list[Detection]] = {}
        for index, path in enumerate(frames):
            image = _read(path)
            sizes[path] = (image.shape[1], image.shape[0])
            found[path] = detector(Frame(image=image, source=str(path), index=index))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(tasks(sizes, found, training.classes, root), indent=1),
                       encoding="utf-8")
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE

    print(f"wrote {len(frames)} tasks to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
