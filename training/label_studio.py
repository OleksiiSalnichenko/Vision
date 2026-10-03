"""Label Studio for drawing boxes: install it, start it, print its labeling interface.

    venv\\Scripts\\python training\\label_studio.py setup    # once, online (pip)
    venv\\Scripts\\python training\\label_studio.py start    # the user runs this
    venv\\Scripts\\python training\\label_studio.py config   # paste into the project

Label Studio lives in its own `venv-labelstudio` in the project root, never in
the project `venv`: it brings Django and its own version pins, which could break
ultralytics/openvino. `setup` is the only networked step here (pip). `start`
serves `data/training` as local files, listens on this machine only and turns
off what Label Studio would otherwise report home.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

from detect import EXIT_USAGE, configure_console  # noqa: E402
from training.settings import (  # noqa: E402
    TRAINING_CONFIG_PATH,
    TrainingConfigError,
    load_training,
)

VENV_DIR = PROJECT_ROOT / "venv-labelstudio"
# The folder Label Studio may serve files from; task URLs are relative to it.
TRAINING_ROOT = PROJECT_ROOT / "data" / "training"
PY_LAUNCHER = "py"
PYTHON_VERSION = "-3.11"
PACKAGE = "label-studio"
EXIT_FAILED = 1

# The labeling interface's tag names; `training/prelabel.py` writes predictions
# against the same two names.
IMAGE_NAME = "image"
LABEL_NAME = "label"

# Bind address. `--host` only names the URL Label Studio puts in links; the
# socket is bound to `--internal-host`, which defaults to 0.0.0.0 (every network
# interface). 127.0.0.1 keeps it on this machine.
# https://github.com/HumanSignal/label-studio/blob/develop/label_studio/server.py
BIND_HOST = "127.0.0.1"

# What Label Studio would otherwise send out, from its settings
# (label_studio/core/settings/base.py; every name is also read with the
# `LABEL_STUDIO_` prefix, label_studio/core/utils/params.py `get_env`):
# - COLLECT_ANALYTICS (default true): usage analytics. Not documented on
#   https://labelstud.io/guide/start -- the switch exists only in the source.
# - LATEST_VERSION_CHECK (default true): asks PyPI for a newer release.
# Sentry error reporting needs SENTRY_DSN / FRONTEND_SENTRY_DSN, which default
# to none in the open-source build, so nothing is sent unless they are set.
# https://github.com/HumanSignal/label-studio/blob/develop/label_studio/core/settings/base.py
NO_REPORTING = {
    "LABEL_STUDIO_COLLECT_ANALYTICS": "false",
    "LABEL_STUDIO_LATEST_VERSION_CHECK": "false",
}


def labeling_config(classes: list[str]) -> str:
    """The Label Studio labeling interface: one image, rectangles for `classes`."""
    labels = "\n".join(f"    <Label value={quoteattr(name)}/>" for name in classes)
    return (
        "<View>\n"
        f'  <Image name="{IMAGE_NAME}" value="$image"/>\n'
        f'  <RectangleLabels name="{LABEL_NAME}" toName="{IMAGE_NAME}">\n'
        f"{labels}\n"
        "  </RectangleLabels>\n"
        "</View>"
    )


def _scripts() -> Path:
    return VENV_DIR / "Scripts"


def _exe() -> Path:
    return _scripts() / "label-studio.exe"


def setup() -> int:
    if _exe().is_file():
        print(f"skip: {PACKAGE} is already installed in {VENV_DIR}")
        return 0
    launcher = shutil.which(PY_LAUNCHER)
    if launcher is None:
        print(f"the Python launcher '{PY_LAUNCHER}' was not found; install Python 3.11 "
              "from python.org with the launcher", file=sys.stderr)
        return EXIT_USAGE
    steps = []
    if not (_scripts() / "python.exe").is_file():
        steps.append([launcher, PYTHON_VERSION, "-m", "venv", str(VENV_DIR)])
    steps.append([str(_scripts() / "python.exe"), "-m", "pip", "install", PACKAGE])
    for command in steps:
        result = subprocess.run(command, check=False)
        if result.returncode:
            print(f"{' '.join(command)} failed with exit code {result.returncode}",
                  file=sys.stderr)
            return EXIT_FAILED
    print(f"installed {PACKAGE} into {VENV_DIR}")
    return 0


def start() -> int:
    if not _exe().is_file():
        print("run training/label_studio.py setup first", file=sys.stderr)
        return EXIT_USAGE
    TRAINING_ROOT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(NO_REPORTING)
    env["LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED"] = "true"
    env["LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT"] = str(TRAINING_ROOT.resolve())
    command = [str(_exe()), "start", "--internal-host", BIND_HOST]
    try:
        result = subprocess.run(command, env=env, check=False)
    except KeyboardInterrupt:  # Ctrl+C is how the user stops the server
        return 0
    return EXIT_FAILED if result.returncode else 0


def config() -> int:
    try:
        cfg = load_training(TRAINING_CONFIG_PATH)
    except (TrainingConfigError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    print(labeling_config(cfg.classes))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Label Studio for drawing training boxes.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help=f"install {PACKAGE} into venv-labelstudio (online)")
    commands.add_parser("start", help="start Label Studio on this machine, serving data/training")
    commands.add_parser("config", help="print the labeling interface for training.classes")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)
    return {"setup": setup, "start": start, "config": config}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
