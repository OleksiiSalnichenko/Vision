"""Everything that leaves the process: JSON, the annotated JPG, console lines.

This is the one module in `core/` allowed to print. It also owns the file
names -- `out\\<stem>_annotated.jpg` and `out\\<stem>.json` -- and the shape of
the JSON, so nothing upstream has to know where its results end up. A repeated
run overwrites: this is a debugging tool, not an archive.

The JSON carries every detection the model produced above `conf_debug`,
including the near misses between `conf_debug` and `conf`, each marked with
`"debug": true`. Those near misses are never drawn and never printed -- seeing
them is the whole reason the file exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from .config import Config
from .types import Detection

_JSON_SUFFIX = ".json"
_IMAGE_FORMAT = ".jpg"
_IMAGE_SUFFIX = f"_annotated{_IMAGE_FORMAT}"
_JSON_INDENT = 2
_CONF_DIGITS = 4
_PCT_DIGITS = 4
# Exactly what Windows refuses in a file name, and nothing more: a Cyrillic
# photo name reads fine (core/source.py), so it has to write out fine too.
_UNSAFE_IN_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def write_json(
    source: str,
    detections: Sequence[Detection],
    cfg: Config,
    debug_detections: Sequence[Detection] = (),
) -> Path | None:
    """Write `out\\<stem>.json` and return its path.

    Returns `None` when `output.save_json` is false. An empty `detections`
    list is written as an empty array, which is a valid answer, not a failure.
    """
    if not cfg.output.save_json:
        return None

    path = _target(source, cfg, _JSON_SUFFIX)
    payload = {
        "source": source,
        "detections": [_as_dict(item, debug=False) for item in detections]
        + [_as_dict(item, debug=True) for item in debug_detections],
    }
    path.write_text(
        json.dumps(payload, indent=_JSON_INDENT) + "\n", encoding="utf-8"
    )
    return path


def write_image(source: str, image: np.ndarray, cfg: Config) -> Path | None:
    """Write the annotated frame as `out\\<stem>_annotated.jpg`.

    Returns `None` when `output.save_image` is false. Raises `OSError` when
    OpenCV refuses to encode the frame, because a silent miss here looks
    exactly like a run that found nothing.

    Encoded in memory and written as bytes rather than through `cv2.imwrite`:
    imwrite goes through a narrow-string path on Windows and fails on any
    folder or file name outside the system code page -- the same trap
    `core/source.py` already steps around when reading.
    """
    if not cfg.output.save_image:
        return None

    path = _target(source, cfg, _IMAGE_SUFFIX)
    encoded, buffer = cv2.imencode(_IMAGE_FORMAT, image)
    if not encoded:
        raise OSError(f"could not encode image: {path}")
    path.write_bytes(buffer.tobytes())
    return path


def print_console(source: str, detections: Sequence[Detection]) -> None:
    """Print one line per detection, under a line naming the source and count.

    The count line is what a user with no detections sees: "0 detections" is
    an answer, an empty window is not.
    """
    print(f"{_stem(source)}: {len(detections)} detections")
    for detection in detections:
        print(f"  {_line(detection)}")


def _line(detection: Detection) -> str:
    """One detection as a console line: class, score, box, offsets, colour."""
    x1, y1, x2, y2 = (int(round(float(value))) for value in detection.bbox)
    text = (
        f"{detection.cls_name} {detection.conf:.2f}"
        f"  box {x1},{y1},{x2},{y2}"
        f"  dx {detection.dx:+d} dy {detection.dy:+d}"
        f"  ({detection.dx_pct:+.1%} / {detection.dy_pct:+.1%})"
    )
    if detection.color:
        text = f"{text}  color {detection.color}"
    return text


def _as_dict(detection: Detection, debug: bool) -> dict[str, Any]:
    """One detection as JSON-ready data, with the near-miss mark."""
    return {
        "cls_id": int(detection.cls_id),
        "cls_name": detection.cls_name,
        "conf": round(float(detection.conf), _CONF_DIGITS),
        "bbox": [round(float(value), 1) for value in detection.bbox],
        "center": [int(round(float(value))) for value in detection.center],
        "dx": int(detection.dx),
        "dy": int(detection.dy),
        "dx_pct": round(float(detection.dx_pct), _PCT_DIGITS),
        "dy_pct": round(float(detection.dy_pct), _PCT_DIGITS),
        "color": detection.color,
        "debug": debug,
    }


def _target(source: str, cfg: Config, suffix: str) -> Path:
    """Path of one output file, with `output.dir` created if it is missing."""
    directory = Path(cfg.output.dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{_stem(source)}{suffix}"


def _stem(source: str) -> str:
    """File name to build outputs from.

    `source` is a path for images and something like "camera:0" for a live
    frame, so the result is scrubbed of anything Windows refuses in a name,
    including the trailing dots and spaces it silently drops.
    """
    stem = Path(source).stem or Path(source).name
    stem = _UNSAFE_IN_NAME.sub("_", stem).rstrip(". ")
    return stem or "frame"
