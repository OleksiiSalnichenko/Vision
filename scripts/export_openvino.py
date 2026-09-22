#!/usr/bin/env python
"""Convert `.pt` weights into an OpenVINO model, once and offline.

OpenVINO is Intel's own runtime and runs the same network noticeably faster on
this CPU than PyTorch does. The model is the same one -- same weights, same
classes -- only in a different file format, so switching the detector to it is
one line of `config.yaml` and nothing else in the project changes.

The export is FP32 with the static input shape `model.imgsz`: a dynamic shape
throws away most of the speed-up, and INT8 needs a calibration dataset that
Ultralytics would download. Because the shape is baked in, changing
`model.imgsz` later means exporting again with `--force`.

Nothing here reaches the network. `core.detector` is imported first, which
switches off Ultralytics' and OpenVINO's telemetry and Ultralytics'
auto-install before either library is loaded.

Usage:
    venv\\Scripts\\python scripts\\export_openvino.py [--weights models/yolo26n.pt] [--force]
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

# First project import, on purpose: it sets the offline switches that
# Ultralytics and OpenVINO only read while they are being imported.
import core.detector  # noqa: E402

from detect import CONFIG_PATH, EXIT_USAGE, configure_console  # noqa: E402

from core.config import load_config  # noqa: E402

MISSING_OPENVINO_MESSAGE = (
    "openvino is not installed -- run: "
    "venv\\Scripts\\python -m pip install -r requirements.txt"
)

WEIGHTS_SUFFIX = ".pt"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_openvino.py",
        description="Export .pt weights to an OpenVINO model folder next to them.",
    )
    parser.add_argument(
        "--weights",
        help="the .pt file to export; defaults to model.weights from config.yaml",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="delete an existing export and convert again",
    )
    return parser.parse_args(argv)


def target_for(weights: Path) -> Path:
    """Where Ultralytics writes the export: `<stem>_openvino_model/` beside the `.pt`."""
    return weights.with_name(weights.stem + core.detector.OPENVINO_SUFFIX)


def is_complete(folder: Path) -> bool:
    """True when the folder holds a model; an interrupted export leaves none."""
    return folder.is_dir() and any(folder.glob("*.xml"))


def export(weights: Path, imgsz: int) -> Path:
    """Run the Ultralytics export and return the folder it wrote."""
    from ultralytics import YOLO  # noqa: PLC0415 -- after core.detector, and only here

    written = YOLO(str(weights)).export(
        format="openvino",
        imgsz=imgsz,
        half=False,
        int8=False,
        dynamic=False,
        device="cpu",
    )
    return Path(written)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        cfg = load_config(CONFIG_PATH)
    except (FileNotFoundError, ValueError) as err:
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE

    weights = Path(args.weights if args.weights is not None else cfg.model.weights)
    if weights.suffix.lower() != WEIGHTS_SUFFIX:
        print(f"only .pt weights can be exported, got: {weights}", file=sys.stderr)
        return EXIT_USAGE
    if not weights.is_file():
        print(core.detector.MISSING_WEIGHTS_MESSAGE, file=sys.stderr)
        return EXIT_USAGE

    target = target_for(weights)
    if is_complete(target) and not args.force:
        print(f"skip: {target}")
        return 0

    if importlib.util.find_spec("openvino") is None:
        print(MISSING_OPENVINO_MESSAGE, file=sys.stderr)
        return EXIT_USAGE

    # Also clears what an interrupted export left behind, so Ultralytics
    # never writes into a folder holding files from an earlier attempt.
    if target.exists():
        shutil.rmtree(target)

    imgsz = cfg.model.imgsz
    written = export(weights, imgsz)
    print(f"exported: {written} (imgsz {imgsz}, FP32)")
    print("the input size is fixed: after changing model.imgsz, export again with --force")
    print("to switch the detector to it, set in config.yaml:")
    print(f"  model.weights: {target.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
