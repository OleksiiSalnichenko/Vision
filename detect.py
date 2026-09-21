#!/usr/bin/env python
"""Phase 1 CLI: a photo goes in, an overlay and a set of numbers come out.

This file is the wiring and nothing else. Every decision it makes is about
order -- read a frame, detect, split, colour, draw, show, save, print, emit --
and every decision about *how* belongs to the module it calls. `core/` knows
nothing about argparse or about how it was started, and that is what keeps the
later phases an addition rather than a rewrite.

The one piece of logic that genuinely lives here is the split between what is
drawn and what is only recorded. `Detector` returns everything from
`conf_debug` upwards in a single list; `core.detector.is_debug` tells the two
groups apart, and this module is the only caller of it. `core.draw` and
`core.output` are handed ready-made lists and never learn a threshold -- if the
split moved into them, a near-miss would start being drawn and printed and
nothing would say so.

Usage:
    venv\\Scripts\\python detect.py --source data/test_images/bus.jpg
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

from core import draw, events, output
from core.config import Config, load_config
from core.detector import Detector, is_debug
from core.source import Source
from core.types import Detection, Frame

log = logging.getLogger("vision.detect")

PROJECT_ROOT = Path(__file__).resolve().parent
# Resolved against this file, not the working directory: the README's commands
# have to work the same from anywhere, and config.yaml ships with the code.
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

WINDOW_TITLE = "Vision"
EXIT_USAGE = 2  # a bad path, a bad config or missing weights -- not a crash

# Keys that close the window early while walking a folder.
_QUIT_KEYS = frozenset({27, ord("q"), ord("Q")})  # 27 is Esc


def configure_console() -> None:
    """Make stdout and stderr survive a file name the console cannot encode.

    The console here is cp1252, so printing a Cyrillic file name raises
    `UnicodeEncodeError` and kills a run that had already done all its work.
    Reading and writing such paths is handled already (`core/source.py`,
    `core/output.py`); this is the same trap one step further along, on the way
    to the terminal. Unencodable characters become escapes instead of an
    exception, which still identifies the file.

    This covers the window that is actually dangerous: everything printed
    before the model loads, which is every usage error. `ultralytics` retunes
    stdout to UTF-8 the moment it is imported, and UTF-8 encodes any name, so
    from there on nothing can raise either -- it is only unreadable on a
    legacy console, never fatal.

    Shared by the other two entry points, `bench.py` and `scripts/grab.py`:
    the trap is theirs as well, and one implementation means one place to fix.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):  # a stream that cannot be retuned
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="detect.py",
        description="Detect objects in a photo or a folder of photos, offline.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="path to an image file or to a folder of images",
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help="name the dominant colour of every drawn object (slower)",
    )
    parser.add_argument(
        "--conf",
        type=_unit_float,
        help="confidence threshold for drawing and printing; overrides model.conf",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        metavar="NAME",
        help='class whitelist, overrides the config list, e.g. --classes person "cell phone"',
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="skip the OpenCV window; files are still written",
    )
    return parser.parse_args(argv)


def _unit_float(text: str) -> float:
    """A confidence on the command line: a number, and inside 0..1."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text}") from None
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"must be between 0 and 1: {text}")
    return value


def with_overrides(cfg: Config, args: argparse.Namespace) -> Config:
    """Return `cfg` with the command-line flags applied over it.

    Two levels and no third: a flag beats the file, the file beats nothing.
    `--conf` also lowers `conf_debug` when it is set below it, because the
    model runs one pass at `conf_debug` and anything under that floor never
    reaches this process at all -- without it `--conf 0.1` would silently
    show the same boxes as `--conf 0.25`.
    """
    model = cfg.model
    if args.conf is not None:
        model = dataclasses.replace(
            model, conf=args.conf, conf_debug=min(model.conf_debug, args.conf)
        )
    classes = args.classes if args.classes is not None else cfg.classes
    return dataclasses.replace(cfg, model=model, classes=classes)


def process(
    frame: Frame, detector: Detector, cfg: Config, want_color: bool
) -> np.ndarray:
    """Run one frame through the pipeline and return the annotated image.

    The split is the whole point of this function: `drawn` is what the user
    sees, what the console lists and what the event bus hears; `near_miss`
    exists only in the JSON.
    """
    detections = detector(frame)
    drawn = [item for item in detections if not is_debug(item, cfg)]
    near_miss = [item for item in detections if is_debug(item, cfg)]

    if want_color:
        _add_colors(frame, drawn)

    canvas = draw.annotate(frame.image, drawn, cfg)

    output.print_console(frame.source, drawn)
    _report(output.write_image(frame.source, canvas, cfg))
    _report(output.write_json(frame.source, drawn, cfg, debug_detections=near_miss))
    if near_miss:
        print(f"  ({len(near_miss)} near-miss below conf, in the JSON only)")

    for detection in drawn:
        events.emit(detection)

    return canvas


def _add_colors(frame: Frame, detections: list[Detection]) -> None:
    """Fill in `color` for the detections that will be drawn.

    Imported here and nowhere else: without `--color` the scikit-learn import
    is never paid for. Only the drawn boxes are sampled -- a colour is a thing
    the user looks at, and a near-miss is never looked at.
    """
    from core.attributes import dominant_color  # noqa: PLC0415 -- behind the flag

    for detection in detections:
        try:
            detection.color = dominant_color(frame.image, detection.bbox)
        except ValueError as err:  # a box too small or too far off the frame
            log.warning("no colour for %s: %s", detection.cls_name, err)


def _report(path: Path | None) -> None:
    """Name a written file, or say nothing when the config turned it off."""
    if path is not None:
        print(f"  wrote {path}")


class Window:
    """The OpenCV preview, and the one place that knows it may not exist.

    A machine with no graphical session raises from `imshow`. That is not a
    failed run: the files are already on disk, so the window steps aside after
    saying so once and everything else continues.
    """

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    def show(self, image: np.ndarray) -> bool:
        """Display one frame. Returns False when the user asked to stop."""
        if not self._enabled:
            return True
        try:
            cv2.imshow(WINDOW_TITLE, image)
            key = cv2.waitKey(0) & 0xFF
        except cv2.error as err:
            print(f"No display available, continuing without a window: {err}", file=sys.stderr)
            self._enabled = False
            return True
        return key not in _QUIT_KEYS

    def close(self) -> None:
        if self._enabled:
            cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    configure_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        cfg = with_overrides(load_config(CONFIG_PATH), args)
        source = Source(args.source, cfg)
        detector = Detector(cfg)
    except (FileNotFoundError, ValueError) as err:
        # One sentence, naming the path: a missing photo is a typo, not a bug,
        # and a traceback would bury the only line that matters.
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE

    window = Window(enabled=not args.no_window)
    try:
        for frame in source:
            canvas = process(frame, detector, cfg, args.color)
            if not window.show(canvas):
                break
    finally:
        window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
