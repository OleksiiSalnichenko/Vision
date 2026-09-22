#!/usr/bin/env python
"""The CLI: a photo, a folder, a video file or a webcam goes in; an overlay,
a set of numbers and -- on a stream -- rule events come out.

This file is the wiring and nothing else. Every decision it makes is about
order -- read a frame, detect, track, split, colour, choose the target, draw,
fire rules, save, show -- and every decision about *how* belongs to the module
it calls. `core/` knows nothing about argparse or about how it was started,
and that is what keeps the later phases an addition rather than a rewrite.

Two branches share it. `run_images` is phase 1 unchanged: one frame at a time,
a JSON and a JPG per photo, a console line per detection, and the event bus
hears every drawn detection. `run_stream` handles video and webcams: ByteTrack
ids, a target, `rules.yaml`, one JSONL line per frame, and a console that
prints rule events only.

The one piece of logic that genuinely lives here is the split between what is
drawn and what is only recorded. `Detector` returns everything from
`conf_debug` upwards in a single list; `core.detector.is_debug` tells the two
groups apart, and this module is the only caller of it. `core.draw` and
`core.output` are handed ready-made lists and never learn a threshold -- if the
split moved into them, a near-miss would start being drawn and printed and
nothing would say so.

Usage:
    venv\\Scripts\\python detect.py --source data/test_images/bus.jpg
    venv\\Scripts\\python detect.py --source clip.mp4
    venv\\Scripts\\python detect.py --source camera:0
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import logging
import sys
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from core import aim, draw, events, output
from core.config import Config, load_config
from core.detector import Detector, is_debug
from core.rules import CALL, RuleEngine, RuleSet, load_rules
from core.source import Source
from core.target import Targeting, TargetState
from core.tracker import Tracker
from core.types import Detection, Frame

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

# Frames the on-screen FPS is averaged over: long enough not to flicker,
# short enough to follow a real slowdown within a couple of seconds.
_FPS_WINDOW = 30


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
            canvas = process(frame, detector, cfg, args.color)
            if not window.show(canvas):
                break
    finally:
        window.close()
    return 0


def run_stream(source: Source, detector: Detector, cfg: Config, args: argparse.Namespace,
               window: Window) -> int:
    """A video file or a webcam: track, target, rules, JSONL, and events only.

    Returns 0 at the end of the file, on `q`/`Esc` and on Ctrl+C; 2 when the
    rules cannot be used or the output cannot be written; 1 when the camera
    stops delivering mid-run. Every path closes the files and prints the
    summary line, so an interrupted run still leaves a whole JSONL and a
    playable video.
    """
    hooked = False
    try:
        rule_set = load_rules(PROJECT_ROOT / cfg.rules.file)
        if rule_set.calls():
            hooked = True
            _load_handlers(rule_set)
    except (FileNotFoundError, ValueError) as err:
        print(f"{err}", file=sys.stderr)
        if hooked:
            events.clear()
        return EXIT_USAGE

    try:
        return _stream(source, detector, cfg, args, window, rule_set)
    finally:
        if hooked:
            # The registry is module state: the next stream loads the file anew.
            events.clear()


def _load_handlers(rule_set: RuleSet) -> None:
    """Run `handlers.py` so its `@on_detect` functions register, then check names.

    Loaded from its path rather than imported, so a second stream in the same
    process registers the functions again after `events.clear()`. Raises
    `FileNotFoundError` when the file is missing and `ValueError` naming the
    first function a rule calls that nothing registered.
    """
    if not HANDLERS_PATH.is_file():
        raise FileNotFoundError(f"handlers file not found: {HANDLERS_PATH}")
    spec = importlib.util.spec_from_file_location("handlers", HANDLERS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    registered = events.names()
    for name in sorted(rule_set.calls()):
        if name not in registered:
            raise ValueError(f"unknown handler in rules.yaml: {name}")
    _warn_unreachable(rule_set)


def _warn_unreachable(rule_set: RuleSet) -> None:
    """Warn once per rule whose class no handler it calls will ever accept.

    `events.call` keeps the handler's class filter, so a rule on `person`
    calling a handler registered for `cell phone` would fire and do nothing.
    """
    for rule in rule_set.rules:
        if rule.cls is None:
            continue
        for action in rule.actions:
            if not (isinstance(action, tuple) and action[0] == CALL):
                continue
            classes = _handler_classes(action[1])
            if None not in classes and rule.cls not in classes:
                log.warning(
                    "rule %s is on %s, but %s only listens to %s; it will never run",
                    rule.name, rule.cls, action[1], ", ".join(sorted(classes)),
                )


def _handler_classes(name: str) -> set[str | None]:
    """The classes the handlers named `name` subscribe to; None means every class.

    `core.events` offers no public view of the class filter, so this reads its
    registry directly.
    """
    return {
        cls
        for cls, handlers in events._handlers.items()  # noqa: SLF001
        for handler in handlers
        if handler.__name__ == name
    }


def _stream(source: Source, detector: Detector, cfg: Config, args: argparse.Namespace,
            window: Window, rule_set: RuleSet) -> int:
    """The frame loop of `run_stream`, once the rules and handlers are in place."""
    # A new tracker, target and rule engine per stream: rule cooldowns are keyed
    # by track id, and a new tracker numbers its tracks from 1 again.
    tracker = Tracker(cfg)
    targeting = Targeting(cfg)
    engine = RuleEngine(rule_set)
    # A camera is never a file on disk; only a video file gets an .mp4 back.
    is_video = Path(str(args.source)).is_file()

    on_screen: list[Detection] = []  # the drawn detections of the frame shown now
    window.on_click(lambda point: targeting.click(point, on_screen))

    writer: output.StreamWriter | None = None
    ticks: deque[float] = deque(maxlen=_FPS_WINDOW)
    frames = fired = 0
    code = 0
    try:
        for frame in source:
            ticks.append(time.perf_counter())
            detections = tracker.update(frame, detector(frame))
            drawn = [item for item in detections if not is_debug(item, cfg)]
            near_miss = [item for item in detections if is_debug(item, cfg)]
            if args.color:
                _add_colors(frame, drawn)

            height, width = frame.image.shape[:2]
            target = targeting.choose(drawn, (width, height))
            status = _status(target, _fps(ticks))
            canvas = draw.annotate(frame.image, drawn, cfg, target, status)

            for event in engine.update(frame.time, drawn):
                fired += 1
                _act(event, frame, canvas, cfg)

            if writer is None:
                # Named after the first frame, so a bare `0` still writes camera_0.
                writer = output.StreamWriter(
                    frame.source, cfg, source.fps, source.frame_size or (width, height), is_video
                )
            try:
                writer.write(frame, drawn, near_miss, target, canvas)
            except OSError as err:
                print(f"{err}", file=sys.stderr)
                code = EXIT_USAGE
                break
            frames += 1

            on_screen[:] = drawn
            if not window.show(canvas):
                break
    except KeyboardInterrupt:
        pass  # Ctrl+C is how a camera run without a window is stopped
    except OSError as err:  # the camera stopped delivering frames
        print(f"{err}", file=sys.stderr)
        code = EXIT_STREAM_FAILED
    finally:
        paths = writer.close() if writer is not None else []
        window.close()
        output.print_stream_summary(frames, fired, paths)
    return code


def _act(event, frame: Frame, canvas: np.ndarray, cfg: Config) -> None:
    """Carry out one rule event's actions, in the order the rule lists them."""
    for action in event.actions:
        if action == "log":
            output.print_event(event)
        elif action == "save_frame":
            output.write_event_frame(event, frame.source, frame.index, canvas, cfg)
        elif isinstance(action, tuple) and action[0] == CALL:
            events.call(action[1], event.detection)


def _fps(ticks: deque[float]) -> float:
    """Frames per second over the last `_FPS_WINDOW` frames, 0 until there are two."""
    if len(ticks) < 2 or ticks[-1] <= ticks[0]:
        return 0.0
    return (len(ticks) - 1) / (ticks[-1] - ticks[0])


def _status(target: TargetState, fps: float) -> str:
    """The line at the top of the overlay: the target, its arrow, and the FPS."""
    rate = f"{fps:.1f} FPS"
    if target.lost:
        return f"target: lost  {rate}"
    detection = target.detection
    if detection is None:
        return f"target: none  {rate}"
    arrow = aim.aim(detection.dx, detection.dy)  # the servo seam: once a frame, target only
    return (
        f"target #{detection.track_id} {detection.cls_name}  "
        f"dx {detection.dx:+d} dy {detection.dy:+d}  {arrow}  {rate}"
    )


def main(argv: list[str] | None = None) -> int:
    configure_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        cfg = with_overrides(load_config(CONFIG_PATH), args)
        source = Source(args.source, cfg)
        detector = Detector(cfg)
    except (FileNotFoundError, ValueError, OSError) as err:
        # One sentence, naming the path: a missing photo or a busy camera is
        # not a bug, and a traceback would bury the only line that matters.
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE

    window = Window(enabled=not args.no_window, stream=source.is_stream)
    if source.is_stream:
        return run_stream(source, detector, cfg, args, window)
    return run_images(source, detector, cfg, args, window)


if __name__ == "__main__":
    sys.exit(main())
