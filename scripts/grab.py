#!/usr/bin/env python
"""Frames from the real webcam, saved into `data\\test_images\\`.

The last step of the verification order in the brief: a stock photo proves the
install, your own photos prove the idea, the flags prove the knobs, and this
proves the camera the later phases will actually run on. It only writes files --
detection stays `detect.py`'s job, pointed at the folder afterwards.

Frames are spaced by `capture.interval` seconds instead of taken back to back:
consecutive webcam frames are the same picture, and the wait also gives the
sensor time to finish its exposure and white-balance hunt.

Usage:
    venv\\Scripts\\python scripts\\grab.py [--camera 0] [--count N]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

from detect import CONFIG_PATH, EXIT_USAGE, configure_console  # noqa: E402

from core.config import Config, load_config  # noqa: E402

IMAGES_DIR = PROJECT_ROOT / "data" / "test_images"
IMAGE_FORMAT = ".jpg"

# DirectShow opens in well under a second on Windows; the default Media
# Foundation backend can take ten and sometimes never reports a missing camera
# as missing. Elsewhere OpenCV's own choice is the right one.
BACKEND = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY

# A camera index nobody is plugged into makes the backend log a warning of its
# own before returning a closed capture. The sentence below says the same thing
# in one line, and two messages for one problem read like two problems.
cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="grab.py",
        description="Save frames from a webcam into data/test_images.",
    )
    parser.add_argument(
        "--camera",
        type=lambda text: _whole(text, minimum=0),
        help="camera index; overrides capture.camera",
    )
    parser.add_argument(
        "--count",
        type=lambda text: _whole(text, minimum=1),
        help="frames to save; overrides capture.count",
    )
    return parser.parse_args(argv)


def _whole(text: str, minimum: int) -> int:
    """A whole number on the command line, refused below `minimum`.

    `VideoCapture(-1)` quietly opens whatever camera it likes, which is not
    what a user who typed a negative index meant.
    """
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {text}") from None
    if value < minimum:
        raise argparse.ArgumentTypeError(f"must be at least {minimum}: {text}")
    return value


def open_camera(index: int, cfg: Config) -> cv2.VideoCapture:
    """Open one camera at the configured resolution.

    Raises `OSError` naming the index when the camera is missing or held by
    another program -- the two cases look identical from here, and the sentence
    says so rather than guessing.
    """
    capture = cv2.VideoCapture(index, BACKEND)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.capture.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.capture.height)
    if not capture.isOpened():
        capture.release()
        raise OSError(f"camera {index} is not available or is in use by another program")
    return capture


def grab(capture: cv2.VideoCapture, index: int, count: int, interval: float) -> list[Path]:
    """Save `count` frames `interval` seconds apart and return their paths."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    saved: list[Path] = []
    due = time.perf_counter() + interval

    while len(saved) < count:
        ok, image = capture.read()
        if not ok or image is None:
            raise OSError(f"camera {index} stopped returning frames after {len(saved)} frame(s)")
        if time.perf_counter() < due:
            continue
        path = IMAGES_DIR / f"cam{index}_{stamp}_{len(saved) + 1:02d}{IMAGE_FORMAT}"
        _write(path, image)
        saved.append(path)
        print(f"saved {path} ({image.shape[1]}x{image.shape[0]})")
        due = time.perf_counter() + interval

    return saved


def _write(path: Path, image) -> None:
    """Encode in memory and write the bytes.

    Never `cv2.imwrite`: it goes through a narrow-string path on Windows and
    fails silently on any folder outside the system code page -- the same trap
    `core/source.py` and `core/output.py` already step around.
    """
    encoded, buffer = cv2.imencode(IMAGE_FORMAT, image)
    if not encoded:
        raise OSError(f"could not encode frame: {path}")
    path.write_bytes(buffer.tobytes())


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)

    try:
        cfg = load_config(CONFIG_PATH)
    except (FileNotFoundError, ValueError) as err:
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE

    index = args.camera if args.camera is not None else cfg.capture.camera
    count = args.count if args.count is not None else cfg.capture.count

    capture = None
    try:
        capture = open_camera(index, cfg)
        saved = grab(capture, index, count, cfg.capture.interval)
    except OSError as err:
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
        return EXIT_USAGE
    finally:
        if capture is not None:
            capture.release()

    print(f"{len(saved)} frame(s) in {IMAGES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
