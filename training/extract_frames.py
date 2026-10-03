"""Turn a video of an object into training frames: every Nth frame, as JPEG.

    venv\\Scripts\\python training\\extract_frames.py --video D:\\clips\\pen.mp4

Writes `data/training/frames/<stem>/<stem>_<index:06d>.jpg` for every frame
whose index is a multiple of `frames.step` in `training/training.yaml`, then
reports how many frames all videos have produced so far against
`frames.target_total`. Consecutive frames are near-duplicates; every Nth one
keeps the natural variety of angle, blur and light without the repetition.

Fully offline. The video is read through `core.source.Source`, which already
opens paths outside the system code page; frames are written with
`cv2.imencode` + `Path.write_bytes` for the same reason.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

from core.source import Source  # noqa: E402
from detect import EXIT_USAGE, configure_console  # noqa: E402
from training.settings import (  # noqa: E402
    TRAINING_CONFIG_PATH,
    TrainingConfigError,
    load_training,
)

FRAMES_ROOT = PROJECT_ROOT / "data" / "training" / "frames"
FRAME_SUFFIX = ".jpg"


def extract(video: str | Path, out_dir: str | Path, step: int) -> int:
    """Write every `step`-th frame of `video` into `out_dir`; return how many.

    Raises `FileNotFoundError` for a missing file, `ValueError` for one that is
    not a playable video, `OSError` when a frame cannot be written.
    """
    video = Path(video)
    out_dir = Path(out_dir)
    if not video.is_file():
        raise FileNotFoundError(f"video not found: {video}")
    # A Path, never a str: a bare number would be taken for a camera index.
    # A video file never reads the runtime config, so none is handed over.
    with Source(video, None) as source:
        if not source.is_stream:
            raise ValueError(f"not a video: {video}")
        out_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for frame in source:
            if frame.index % step:
                continue
            ok, encoded = cv2.imencode(FRAME_SUFFIX, frame.image)
            if not ok:
                raise OSError(f"cannot encode frame {frame.index} of {video}")
            (out_dir / f"{video.stem}_{frame.index:06d}{FRAME_SUFFIX}").write_bytes(
                encoded.tobytes())
            written += 1
    return written


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save every Nth frame of a video (frames.step in training/training.yaml).")
    parser.add_argument("--video", required=True, help="the video file to cut into frames")
    parser.add_argument(
        "--out", help="folder for the frames (default: data/training/frames/<video name>)")
    parser.add_argument(
        "--force", action="store_true",
        help="write into a folder that already has files (frames of the same name are replaced)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)
    video = Path(args.video)
    out_dir = Path(args.out) if args.out else FRAMES_ROOT / video.stem

    try:
        cfg = load_training(TRAINING_CONFIG_PATH)
    except (TrainingConfigError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE

    if not video.is_file():
        print(f"video not found: {video}", file=sys.stderr)
        return EXIT_USAGE
    if out_dir.is_dir() and any(out_dir.iterdir()) and not args.force:
        print(f"{out_dir} already has files; pass --force to write into it anyway",
              file=sys.stderr)
        return EXIT_USAGE

    try:
        written = extract(video, out_dir, cfg.frames.step)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE

    print(f"wrote {written} frames to {out_dir}")
    total = sum(1 for _ in FRAMES_ROOT.rglob(f"*{FRAME_SUFFIX}")) if FRAMES_ROOT.is_dir() else 0
    print(f"total {total} frames in {_shown(FRAMES_ROOT)} (target ~{cfg.frames.target_total})")
    return 0


def _shown(path: Path) -> str:
    """`path` relative to the project when it is inside it, as the user typed it."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
