#!/usr/bin/env python
"""How long one frame costs on this machine.

The number that matters for phase 2 is seconds per frame on a CPU-only box, so
that is what this prints -- with a warm-up first. The first inference pays for
lazy kernel initialisation and the first allocation of every buffer the model
uses; folding it into the average makes a ten-run benchmark report a machine
noticeably slower than it is, and the error shrinks as the run count grows,
which is exactly the shape that hides a measurement bug.

Frames are decoded once, before the clock starts: this measures inference, not
the disk.

Usage:
    venv\\Scripts\\python bench.py --source data/test_images/bus.jpg [--runs N]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from detect import CONFIG_PATH, EXIT_USAGE, configure_console

from core.config import load_config
from core.detector import Detector
from core.source import Source
from core.types import Frame

log = logging.getLogger("vision.bench")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bench.py",
        description="Measure seconds per frame and FPS for the configured model.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="path to an image file or to a folder of images",
    )
    parser.add_argument(
        "--runs",
        type=_positive_int,
        help="measured passes over the source; overrides bench.runs",
    )
    return parser.parse_args(argv)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {text}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1: {text}")
    return value


def one_pass(detector: Detector, frames: list[Frame]) -> float:
    """Run the detector over every frame once and return the seconds it took."""
    started = time.perf_counter()
    for frame in frames:
        detector(frame)
    return time.perf_counter() - started


def measure(detector: Detector, frames: list[Frame], runs: int, warmup: int) -> list[float]:
    """Return the seconds-per-frame of each measured pass, warm-up discarded."""
    for _ in range(warmup):
        one_pass(detector, frames)
    return [one_pass(detector, frames) / len(frames) for _ in range(runs)]


def report(source: str, frames: int, runs: int, warmup: int, timings: list[float]) -> None:
    """Print the measurement: seconds per frame first, FPS beside it."""
    mean = sum(timings) / len(timings)
    print(f"source:  {source} ({frames} frame(s))")
    print(f"warmup:  {warmup} pass(es), discarded")
    print(f"runs:    {runs} pass(es), {runs * frames} frame(s) timed")
    print(
        f"seconds per frame: {mean:.4f}"
        f"  (min {min(timings):.4f}, max {max(timings):.4f})"
    )
    print(f"FPS: {1.0 / mean:.2f}")


def main(argv: list[str] | None = None) -> int:
    configure_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        cfg = load_config(CONFIG_PATH)
        frames = list(Source(args.source, cfg))
        detector = Detector(cfg)
    except (FileNotFoundError, ValueError) as err:
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE

    runs = args.runs if args.runs is not None else cfg.bench.runs
    warmup = cfg.bench.warmup

    print(f"model:   {cfg.model.weights} (imgsz {cfg.model.imgsz})")
    timings = measure(detector, frames, runs, warmup)
    report(args.source, len(frames), runs, warmup, timings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
