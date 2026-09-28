#!/usr/bin/env python
"""The CLI: a photo, a folder, a video file or a webcam goes in; an overlay,
a set of numbers and -- on a stream -- rule events come out.

This file is flags, console and exit codes, and nothing else. The order of a
frame -- detect, track, split, colour, choose the target, draw, fire rules,
save -- lives in `core.pipeline`, which the desktop app runs as well, so the
two can never drift apart. `core/` knows nothing about argparse or about how
it was started, and that is what keeps the later phases an addition rather
than a rewrite.

Two branches share it. `run_images` is phase 1 unchanged: one frame at a time,
a JSON and a JPG per photo, a console line per detection, and the event bus
hears every drawn detection. `run_stream` handles video and webcams: ByteTrack
ids, a target, `rules.yaml`, one JSONL line per frame, and a console that
prints rule events only.

The split between what is drawn and what is only recorded is made in
`core.pipeline` and nowhere else; this module is handed the two lists.

Usage:
    venv\\Scripts\\python detect.py --source data/test_images/bus.jpg
    venv\\Scripts\\python detect.py --source clip.mp4
    venv\\Scripts\\python detect.py --source camera:0
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from core import events, output, pipeline
from core.config import Config, load_config
from core.detector import Detector, require_weights
from core.rules import RuleSet
from core.source import Source, is_stream_spec
from core.types import Frame

log = logging.getLogger("vision.detect")

PROJECT_ROOT = Path(__file__).resolve().parent
# Resolved against this file, not the working directory: the README's commands
# have to work the same from anywhere, and config.yaml ships with the code.
# `rules.file` in the config is resolved against the same root.
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
# The user's functions for `{call: name}` rule actions. Loaded from this path
# only when a rule calls something, and freshly on every stream.
HANDLERS_PATH = PROJECT_ROOT / "handlers.py"

WINDOW_TITLE = "Vision"
EXIT_USAGE = 2  # a bad path, a bad config or missing weights -- not a crash
EXIT_STREAM_FAILED = 1  # the camera went away mid-run; the files are still whole

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
        description="Detect objects in photos, video files or a webcam, offline.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="image, folder of images, video file, or camera:N",
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
    """Run one photo through the pipeline, say what was found, and return the overlay.

    `drawn` is what the user sees, what the console lists and what the event
    bus hears; `near_miss` exists only in the JSON. The split itself is made
    in `core.pipeline`.
    """
    result = pipeline.process_still(frame, detector, cfg, want_color)

    output.print_console(frame.source, result.drawn)
    # Each file is named as soon as it is on disk, so a failing JSON write
    # still leaves the image's line on the console.
    pipeline.save_still(
        frame.source, result, cfg, on_written=lambda path: print(f"  wrote {path}")
    )
    if result.near_miss:
        print(f"  ({len(result.near_miss)} near-miss below conf, in the JSON only)")

    for detection in result.drawn:
        events.emit(detection)

    return result.canvas


def want_color(args: argparse.Namespace, cfg: Config) -> bool:
    """Colour is drawn when `--color` is given or `display.color` is true."""
    return bool(args.color) or cfg.display.color


class Window:
    """The OpenCV preview, and the one place that knows it may not exist.

    A machine with no graphical session raises from `imshow`. That is not a
    failed run: the files are already on disk, so the window steps aside after
    saying so once and everything else continues.
    """

    def __init__(self, enabled: bool, stream: bool = False) -> None:
        self._enabled = enabled
        # A photo waits for a key; a stream only polls, or it would stop on
        # every frame.
        self._wait_ms = 1 if stream else 0
        self._on_click: Callable[[tuple[float, float]], None] | None = None
        self._opened = False

    def on_click(self, callback: Callable[[tuple[float, float]], None]) -> None:
        """Call `callback((x, y))` on every left click, in image pixels.

        The window is created with its default autosize, so a pixel of the
        window is a pixel of the frame and the point needs no scaling.
        """
        self._on_click = callback

    def show(self, image: np.ndarray) -> bool:
        """Display one frame. Returns False when the user asked to stop."""
        if not self._enabled:
            return True
        try:
            if not self._opened:
                self._open()
            cv2.imshow(WINDOW_TITLE, image)
            key = cv2.waitKey(self._wait_ms) & 0xFF
        except cv2.error as err:
            print(f"No display available, continuing without a window: {err}", file=sys.stderr)
            self._enabled = False
            return True
        return key not in _QUIT_KEYS

    def _open(self) -> None:
        # A mouse callback needs the window to exist before the first imshow.
        cv2.namedWindow(WINDOW_TITLE)
        if self._on_click is not None:
            cv2.setMouseCallback(WINDOW_TITLE, self._mouse)
        self._opened = True

    def _mouse(self, event: int, x: int, y: int, flags: int, param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN and self._on_click is not None:
            self._on_click((float(x), float(y)))

    def close(self) -> None:
        if self._enabled:
            cv2.destroyAllWindows()


def run_images(source: Source, detector: Detector, cfg: Config, args: argparse.Namespace,
               window: Window) -> int:
    """Phase 1, unchanged: a photo or a folder, one frame at a time."""
    try:
        for frame in source:
            canvas = process(frame, detector, cfg, want_color(args, cfg))
            if not window.show(canvas):
                break
    finally:
        window.close()
    return 0


def run_stream(source: Source, detector: Detector, cfg: Config, args: argparse.Namespace,
               window: Window, rule_set: RuleSet | None = None) -> int:
    """A video file or a webcam: track, target, rules, JSONL, and events only.

    Returns 0 at the end of the file, on `q`/`Esc` and on Ctrl+C; 2 when the
    rules cannot be used or a file cannot be written; 1 when the camera stops
    delivering mid-run. Every path closes the files and prints the summary
    line, so an interrupted run still leaves a whole JSONL and a playable video.

    `rule_set` is the one `main` prepared before the camera was opened; given
    none, the rules and handlers are loaded here and unhooked on the way out.
    The source itself is closed by whoever opened it.
    """
    owned = rule_set is None
    if owned:
        try:
            rule_set = prepare_rules(cfg)
        except (FileNotFoundError, ValueError) as err:
            print(f"{err}", file=sys.stderr)
            return EXIT_USAGE

    try:
        return _stream(source, detector, cfg, args, window, rule_set)
    finally:
        if owned and rule_set.calls():
            # The registry is module state: the next stream loads the file anew.
            events.clear()


def prepare_rules(cfg: Config) -> RuleSet:
    """Load `rules.yaml` and, when a rule calls a function, `handlers.py`.

    Raises `FileNotFoundError` or `ValueError` with one sentence; on a failure
    the bus is left empty. On success the handlers stay registered, and the
    caller clears the bus once the stream is over. `HANDLERS_PATH` is read at
    call time.
    """
    return pipeline.prepare_rules(PROJECT_ROOT / cfg.rules.file, HANDLERS_PATH)


def _stream(source: Source, detector: Detector, cfg: Config, args: argparse.Namespace,
            window: Window, rule_set: RuleSet) -> int:
    """The frame loop of `run_stream`, once the rules and handlers are in place."""
    session = pipeline.StreamSession(
        detector, cfg, rule_set, source.fps, source.frame_size,
        # Only a video file gets an .mp4 back; a camera's frames go to the JSONL.
        is_video=not source.is_camera,
        on_log=lambda event: output.print_event(event),
        want_color=want_color(args, cfg),
    )
    window.on_click(session.click)

    code = 0
    incoming = iter(source)
    try:
        while True:
            # Only reading a frame can mean the camera went away; a file that
            # cannot be written is caught below, and said as such.
            try:
                frame = next(incoming)
            except StopIteration:
                break
            except OSError as err:  # the camera stopped delivering frames
                print(f"{err}", file=sys.stderr)
                code = EXIT_STREAM_FAILED
                break

            try:
                result = session.step(frame)
            except pipeline.StreamWriteError as err:
                # Only an event frame, the JSONL or the .mp4 that could not be
                # written, named in err. An OSError from the model, the tracker,
                # drawing or a handler is not caught here and propagates.
                print(f"{err}", file=sys.stderr)
                code = EXIT_USAGE
                break

            if not window.show(result.canvas):
                break
    except KeyboardInterrupt:
        pass  # Ctrl+C is how a camera run without a window is stopped
    finally:
        # Ends the source's generator now, so a video file's capture is
        # released here rather than whenever the garbage collector gets to it.
        close_frames = getattr(incoming, "close", None)
        if close_frames is not None:
            close_frames()
        paths = session.close()
        window.close()
        output.print_stream_summary(session.frames, session.fired, paths)
    return code


def main(argv: list[str] | None = None) -> int:
    configure_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        cfg = with_overrides(load_config(CONFIG_PATH), args)
        # What only a stream needs is checked before the source is opened: a
        # broken rules.yaml or handlers.py must not switch the webcam on at all.
        rule_set = prepare_rules(cfg) if is_stream_spec(args.source) else None
    except (FileNotFoundError, ValueError, OSError) as err:
        # One sentence, naming the path: a missing photo or a busy camera is
        # not a bug, and a traceback would bury the only line that matters.
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE

    try:
        return _run(args, cfg, rule_set)
    finally:
        if rule_set is not None and rule_set.calls():
            events.clear()  # the registry is module state; leave it as found


def _run(args: argparse.Namespace, cfg: Config, rule_set: RuleSet | None) -> int:
    """Open the source, load the model, and hand both to the right branch."""
    try:
        # Missing weights must not switch a webcam on only to switch it off.
        require_weights(cfg)
        source = Source(args.source, cfg)
    except (FileNotFoundError, ValueError, OSError) as err:
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE

    # A webcam is held from here on. The `with` releases it on every way out --
    # the end, `q`/`Esc`, Ctrl+C, a failure, even a model that will not load --
    # rather than whenever the garbage collector gets to it.
    with source:
        try:
            detector = Detector(cfg)
        except (FileNotFoundError, ValueError, OSError) as err:
            print(f"{err}", file=sys.stderr)
            return EXIT_USAGE

        window = Window(enabled=not args.no_window, stream=source.is_stream)
        if source.is_stream:
            return run_stream(source, detector, cfg, args, window, rule_set)
        return run_images(source, detector, cfg, args, window)


if __name__ == "__main__":
    sys.exit(main())
