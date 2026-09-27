"""Everything that leaves the process: JSON, the annotated JPG, console lines.

This is the one module in `core/` allowed to print. It also owns the file
names -- `out\\<stem>_annotated.jpg` and `out\\<stem>.json` -- and the shape of
the JSON, so nothing upstream has to know where its results end up. A repeated
run overwrites: this is a debugging tool, not an archive.

The JSON carries every detection the model produced above `conf_debug`,
including the near misses between `conf_debug` and `conf`, each marked with
`"debug": true`. Those near misses are never drawn and never printed -- seeing
them is the whole reason the file exists.

A stream (video file or camera) prints nothing per frame. `StreamWriter`
leaves `out\\<stem>.jsonl` -- one line per frame, the same detection shape plus
`"track_id"` -- and, for a video file, `out\\<stem>_annotated.mp4`. Rule events
print one line each (`print_event`), may save their frame under `out\\events\\`
(`write_event_frame`), and the run ends with `print_stream_summary`. The photo
JSON never carries `"track_id"`: its shape is phase 1's, unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from .config import Config
from .target import TargetState
from .types import Detection, Frame

_JSON_SUFFIX = ".json"
_IMAGE_FORMAT = ".jpg"
_IMAGE_SUFFIX = f"_annotated{_IMAGE_FORMAT}"
_JSON_INDENT = 2
_CONF_DIGITS = 4
_PCT_DIGITS = 4
# Exactly what Windows refuses in a file name, and nothing more: a Cyrillic
# photo name reads fine (core/source.py), so it has to write out fine too.
_UNSAFE_IN_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_JSONL_SUFFIX = ".jsonl"
_TIME_DIGITS = 3
_VIDEO_SUFFIX = "_annotated.mp4"
_VIDEO_CODEC = "mp4v"  # ships with every OpenCV wheel; no extra DLL to hunt for
# A stream that reports no frame rate still needs one in the container; 25 is
# the PAL rate most webcams and clips land near, so playback speed stays sane.
_FALLBACK_FPS = 25.0
# cv2.VideoWriter takes a narrow-string path on Windows, so the file is written
# under a plain-ASCII name first and renamed once it is closed.
_NOT_ASCII_NAME = re.compile(r"[^A-Za-z0-9_.-]")
_PART_TEMPLATE = ".{name}.part.mp4"
_EVENTS_DIR = "events"


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


class StreamWriter:
    """What one video or camera stream leaves on disk, frame by frame.

    `out\\<stem>.jsonl` gets one line per frame (when `output.save_json`),
    flushed as soon as it is written so an interrupted run keeps every line up
    to the last frame. With `video=True` (a video file, never a camera) and
    `output.save_image`, the annotated frames also go to
    `out\\<stem>_annotated.mp4` at the stream's own frame rate.

    Use it as a context manager: `close()` runs on the way out of the `with`
    block, exception or not, so Ctrl+C still leaves a playable `.mp4` and a
    whole JSONL. Files are opened on the first `write`, so a stream that
    delivered nothing leaves nothing behind.
    """

    def __init__(
        self,
        source: str,
        cfg: Config,
        fps: float,
        frame_size: tuple[int, int],
        video: bool,
    ) -> None:
        self._source = source
        self._cfg = cfg
        self._fps = fps if fps > 0 else _FALLBACK_FPS
        self._frame_size = (int(frame_size[0]), int(frame_size[1]))
        self._want_json = cfg.output.save_json
        self._want_video = video and cfg.output.save_image
        self._jsonl = None
        self._jsonl_path: Path | None = None
        self._video: cv2.VideoWriter | None = None
        self._part_path: Path | None = None
        self._closed: list[Path] | None = None

    def __enter__(self) -> StreamWriter:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    def write(
        self,
        frame: Frame,
        drawn: Sequence[Detection],
        near_miss: Sequence[Detection],
        target: TargetState | None,
        canvas: np.ndarray,
    ) -> None:
        """Record one frame: a JSONL line and, for a video file, its overlay.

        `drawn` and `near_miss` are the split `detect.py` already made; the
        near misses go to the JSONL only, marked `"debug": true`. `canvas`
        is the annotated frame and must be `frame_size`.
        """
        if self._closed is not None:
            raise ValueError("StreamWriter is closed")
        # Checked before anything is written, so the JSONL and the .mp4
        # never disagree by a frame.
        if self._want_video:
            self._check_size(canvas)
        if self._want_json:
            self._write_line(frame, drawn, near_miss, target)
        if self._want_video:
            self._write_video(canvas)

    def close(self) -> list[Path]:
        """Close every file and return the paths written, in a stable order.

        Idempotent: a second call returns the same list and touches nothing.
        """
        if self._closed is not None:
            return list(self._closed)

        written: list[Path] = []
        try:
            if self._jsonl is not None:
                self._jsonl.close()
                written.append(self._jsonl_path)
        finally:
            if self._video is not None:
                self._video.release()
                final = _target(self._source, self._cfg, _VIDEO_SUFFIX)
                self._part_path.replace(final)
                written.append(final)
            self._closed = written
        return list(written)

    def _write_line(
        self,
        frame: Frame,
        drawn: Sequence[Detection],
        near_miss: Sequence[Detection],
        target: TargetState | None,
    ) -> None:
        if self._jsonl is None:
            self._jsonl_path = _target(self._source, self._cfg, _JSONL_SUFFIX)
            self._jsonl = self._jsonl_path.open("w", encoding="utf-8")
        row = {
            "source": frame.source,
            "index": int(frame.index),
            "time": round(float(frame.time), _TIME_DIGITS),
            "target": _target_dict(target),
            "detections": [_stream_dict(item, debug=False) for item in drawn]
            + [_stream_dict(item, debug=True) for item in near_miss],
        }
        self._jsonl.write(json.dumps(row) + "\n")
        self._jsonl.flush()

    def _check_size(self, canvas: np.ndarray) -> None:
        height, width = canvas.shape[:2]
        if (width, height) != self._frame_size:
            raise ValueError(
                f"frame is {width}x{height}, the video was opened for "
                f"{self._frame_size[0]}x{self._frame_size[1]}"
            )

    def _write_video(self, canvas: np.ndarray) -> None:
        if self._video is None:
            self._video = self._open_video()
        self._video.write(canvas)

    def _open_video(self) -> cv2.VideoWriter:
        ascii_stem = _NOT_ASCII_NAME.sub("_", _stem(self._source))
        self._part_path = _target(self._source, self._cfg, "").with_name(
            _PART_TEMPLATE.format(name=ascii_stem)
        )
        writer = cv2.VideoWriter(
            str(self._part_path),
            cv2.VideoWriter_fourcc(*_VIDEO_CODEC),
            self._fps,
            self._frame_size,
        )
        if not writer.isOpened():
            writer.release()
            raise OSError(f"could not open video for writing: {self._part_path}")
        return writer


def print_event(event: Any) -> None:
    """Print one rule event: the line `format_event` builds."""
    print(format_event(event))


def format_event(event: Any) -> str:
    """One rule event as a line: `[00:12.4] person_appeared  person #7 0.83  dx +120 dy -40`.

    `event` is a `core.rules.Event`; only `rule`, `time` and `detection` are
    read, so this module does not import the rules engine. The console and the
    desktop app's event list show this same string.
    """
    detection = event.detection
    track = f" #{detection.track_id}" if detection.track_id is not None else ""
    return (
        f"[{_clock(event.time)}] {event.rule}  "
        f"{detection.cls_name}{track} {detection.conf:.2f}  "
        f"dx {detection.dx:+d} dy {detection.dy:+d}"
    )


def write_event_frame(
    event: Any, source: str, index: int, image: np.ndarray, cfg: Config
) -> Path:
    """Write `image` as `<output.dir>\\events\\<stem>_<rule>_<index>.jpg`.

    `index` is the frame number, which an `Event` does not carry. Written
    whatever `output.save_image` says: a `save_frame` action asked for it.
    Raises `OSError` when OpenCV refuses to encode the frame.
    """
    directory = Path(cfg.output.dir) / _EVENTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    rule = _UNSAFE_IN_NAME.sub("_", str(event.rule))
    path = directory / f"{_stem(source)}_{rule}_{int(index)}{_IMAGE_FORMAT}"
    encoded, buffer = cv2.imencode(_IMAGE_FORMAT, image)
    if not encoded:
        raise OSError(f"could not encode image: {path}")
    path.write_bytes(buffer.tobytes())
    return path


def print_stream_summary(frames: int, events: int, paths: Sequence[Path]) -> None:
    """Print the one line a stream ends with: the line `format_summary` builds."""
    print(format_summary(frames, events, paths))


def format_summary(frames: int, events: int, paths: Sequence[Path]) -> str:
    """The one line a stream ends with: `N frames, M events, wrote a, b`."""
    wrote = ", ".join(str(path) for path in paths) if paths else "nothing"
    return f"{frames} frames, {events} events, wrote {wrote}"


def _clock(seconds: float) -> str:
    """Stream time as `mm:ss.s`; rounded first, so 59.96 s reads `01:00.0`."""
    tenths = int(round(float(seconds) * 10))
    minutes, rest = divmod(tenths, 600)
    return f"{minutes:02d}:{rest / 10:04.1f}"


def _target_dict(target: TargetState | None) -> dict[str, Any] | None:
    """The target as JSONL data, or `None` when there is neither target nor lock."""
    if target is None or (target.detection is None and not target.locked):
        return None
    detection = target.detection
    return {
        "track_id": None if detection is None else _track_id(detection),
        "locked": bool(target.locked),
        "lost": bool(target.lost),
    }


def _stream_dict(detection: Detection, debug: bool) -> dict[str, Any]:
    """A detection for the JSONL: the photo shape plus `track_id`."""
    return {"track_id": _track_id(detection), **_as_dict(detection, debug)}


def _track_id(detection: Detection) -> int | None:
    return None if detection.track_id is None else int(detection.track_id)


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
