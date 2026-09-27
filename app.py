"""The Vision desktop app: everything `detect.py` does, in a window.

    venv\\Scripts\\python app.py [--source <photo | folder | video | camera:N>]

The model loads in the background as the window opens. A broken `config.yaml`
is one sentence on stderr and exit code 2, with no window at all; everything
after that -- missing weights, a busy camera, a broken `rules.yaml` -- is a
message in the window, and the app stays open.
"""

from __future__ import annotations

import argparse
import logging
import sys

import yaml

# `core.detector` first: it switches Ultralytics offline before anything imports it.
from core.detector import Detector
from core.config import Config, load_config
from core.source import Source
from detect import CONFIG_PATH, EXIT_USAGE, configure_console, not_yaml_text


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Detect objects in photos, video files or a webcam, offline, in a window.",
    )
    parser.add_argument(
        "--source",
        help="open this at start: image, folder of images, video file, or camera:N",
    )
    return parser.parse_args(argv)


def make_worker(cfg: Config):
    """The worker the window drives: the real model and the real sources."""
    from ui.worker import PipelineWorker

    return PipelineWorker(cfg, Detector, Source)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        cfg = load_config(CONFIG_PATH)
    except (ValueError, OSError) as err:  # ConfigError is a ValueError; a missing file an OSError
        print(f"{err}", file=sys.stderr)
        return EXIT_USAGE
    except yaml.YAMLError:
        print(not_yaml_text(CONFIG_PATH), file=sys.stderr)
        return EXIT_USAGE

    # Qt only now: a usage error above never needs it.
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow

    qt_app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow(cfg, make_worker)
    if args.source:
        # Queued behind the model load, so it opens as soon as the model is in.
        window.open_source(args.source)
    window.show()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
