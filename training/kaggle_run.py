"""Train on Kaggle through the `kaggle` command-line tool.

    venv\\Scripts\\python training\\kaggle_run.py check
    venv\\Scripts\\python training\\kaggle_run.py upload --build NAME [--yes]
    venv\\Scripts\\python training\\kaggle_run.py train [--rough] [--yes]
    venv\\Scripts\\python training\\kaggle_run.py status [--yes]
    venv\\Scripts\\python training\\kaggle_run.py fetch --name N [--force] [--yes]

`check` is local: is `kaggle` installed, does `%USERPROFILE%\\.kaggle\\kaggle.json`
exist (its content is never read), is `training.kaggle.username` filled in.
Every other subcommand talks to Kaggle, and without `--yes` it only prints what
it would send where, and exits 0 having sent nothing.

`upload` sends `data/training/build/NAME` as the private dataset
`username/dataset_slug`; `train` pushes `training/kaggle/train.py` as a private
GPU script kernel reading that dataset and, unless `--rough`, the public COCO
dataset `kaggle.coco_dataset`; `status` shows the kernel's state; `fetch` brings
its `best.pt` and `metrics.json` home as `models/N.pt` and `models/N.metrics.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # run as a script, not an installed package
    sys.path.insert(0, str(PROJECT_ROOT))

from detect import EXIT_USAGE, configure_console  # noqa: E402
from training.settings import (  # noqa: E402
    TRAINING_CONFIG_PATH,
    TrainingConfigError,
    load_training,
)

EXIT_KAGGLE_FAILED = 1
BUILD_ROOT = PROJECT_ROOT / "data" / "training" / "build"
MODELS_DIR = PROJECT_ROOT / "models"
KAGGLE_JSON = Path.home() / ".kaggle" / "kaggle.json"
TRAIN_SCRIPT = Path(__file__).resolve().parent / "kaggle" / "train.py"
SETTINGS_SCRIPT = Path(__file__).resolve().parent / "settings.py"
SETTINGS_SLOT = "_SETTINGS_SOURCE: str | None = None"
DATASET_LICENSE = "CC0-1.0"
# How the kaggle CLI reports a dataset it does not have ("404 - Not Found", or
# "404 Client Error: Not Found ..." in newer versions), as opposed to 401/403/network.
NOT_FOUND = r"\b404\b"

NO_KAGGLE_MESSAGE = (
    "kaggle is not installed -- run: "
    "venv\\Scripts\\python -m pip install -r requirements-training.txt")
NO_USERNAME_MESSAGE = "set training.kaggle.username in training/training.yaml"


def _find_kaggle() -> list[str] | None:
    """The command that runs `kaggle`: the venv's own first, then PATH."""
    beside = Path(sys.executable).with_name("kaggle.exe")
    if beside.is_file():
        return [str(beside)]
    found = shutil.which("kaggle")
    return [found] if found else None


# The command prefix that runs the kaggle CLI; tests replace it with a fake.
KAGGLE_EXE: list[str] | None = _find_kaggle()


class UsageError(Exception):
    """One sentence for stderr; the command exits with EXIT_USAGE."""


class _KaggleFailed(Exception):
    """The kaggle CLI itself failed; it has already said why on the console."""


def _kaggle(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """Run the kaggle CLI; its own output goes to the console unless `capture`."""
    try:
        return subprocess.run([*KAGGLE_EXE, *args], capture_output=capture, text=True,
                              errors="replace", check=False)
    except OSError as error:  # the executable is gone or will not start
        raise _KaggleFailed(f"cannot run {KAGGLE_EXE[0]}: {error}") from error


def _run(*args: str) -> None:
    code = _kaggle(*args).returncode
    if code:
        raise _KaggleFailed(f"kaggle {' '.join(args[:2])} failed (exit {code})")


def _dataset_exists(dataset: str) -> bool:
    """Whether Kaggle has `dataset`; any failure other than "not found" is raised."""
    done = _kaggle("datasets", "status", dataset, capture=True)
    if done.returncode == 0:
        return True
    said = f"{done.stdout or ''}\n{done.stderr or ''}".strip()
    if re.search(NOT_FOUND, said):
        return False
    cause = said.splitlines()[-1] if said else "no output"
    raise _KaggleFailed(f"kaggle datasets status failed (exit {done.returncode}): {cause}")


def _size_mb(folder: Path) -> float:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) / 1e6


def check(cfg) -> list[str]:
    """Every reason the network subcommands could not run, one sentence each."""
    problems = []
    if KAGGLE_EXE is None:
        problems.append(NO_KAGGLE_MESSAGE)
    if not KAGGLE_JSON.is_file():  # existence only: the key never passes through here
        problems.append(f"no Kaggle API key at {KAGGLE_JSON} -- create one on kaggle.com "
                        "(Settings, API, Create New Token) and put the file there")
    if not cfg.kaggle.username.strip():
        problems.append(NO_USERNAME_MESSAGE)
    return problems


def upload(cfg, build_name: str, yes: bool) -> None:
    build = BUILD_ROOT / build_name
    if not build.is_dir():
        raise UsageError(f"build folder not found: {build}")
    dataset = f"{cfg.kaggle.username}/{cfg.kaggle.dataset_slug}"
    if not yes:
        print(f"plan: upload {build} ({_size_mb(build):.1f} MB) "
              f"to Kaggle as the private dataset {dataset}")
        print("nothing sent; run again with --yes to upload")
        return
    exists = _dataset_exists(dataset)
    # The CLI reads the metadata from the folder it uploads; it is gone again
    # afterwards, so the build stays exactly as build_dataset.py wrote it.
    metadata = build / "dataset-metadata.json"
    metadata.write_text(json.dumps({
        "title": cfg.kaggle.dataset_slug,
        "id": dataset,
        "licenses": [{"name": DATASET_LICENSE}],
    }, indent=2), encoding="utf-8")
    try:
        if exists:
            _run("datasets", "version", "-p", str(build), "-m", f"build {build_name}",
                 "--dir-mode", "zip")
        else:  # a new dataset is private unless --public is passed
            _run("datasets", "create", "-p", str(build), "--dir-mode", "zip")
    finally:
        metadata.unlink(missing_ok=True)
    print(f"uploaded {build} as {dataset}")


def train(cfg, rough: bool, yes: bool) -> None:
    kernel = f"{cfg.kaggle.username}/{cfg.kaggle.kernel_slug}"
    sources = [f"{cfg.kaggle.username}/{cfg.kaggle.dataset_slug}"]
    if not rough:
        sources.append(cfg.kaggle.coco_dataset)
    if not yes:
        epochs = cfg.rough.epochs if rough else cfg.train.epochs
        print(f"plan: push {TRAIN_SCRIPT.name} to Kaggle as the private GPU kernel {kernel} "
              f"(internet on for pip), reading {', '.join(sources)}; "
              f"{'rough' if rough else 'full'} mode, {epochs} epochs")
        print("nothing sent; run again with --yes to start training")
        return
    with tempfile.TemporaryDirectory(prefix="vision-kernel-") as tmp:
        folder = Path(tmp)
        (folder / TRAIN_SCRIPT.name).write_text(_bundled_script(), encoding="utf-8")
        (folder / "kernel-metadata.json").write_text(json.dumps({
            "id": kernel,
            "title": cfg.kaggle.kernel_slug,
            "code_file": TRAIN_SCRIPT.name,
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "dataset_sources": sources,
            "competition_sources": [],
            "kernel_sources": [],
        }, indent=2), encoding="utf-8")
        _run("kernels", "push", "-p", str(folder))
    print(f"pushed {kernel}; follow it with: kaggle_run.py status --yes")


def _bundled_script() -> str:
    """`train.py` with `training/settings.py` embedded: a script kernel is one file."""
    script = TRAIN_SCRIPT.read_text(encoding="utf-8")
    if script.count(SETTINGS_SLOT) != 1:
        raise UsageError(f"{TRAIN_SCRIPT} has no single line {SETTINGS_SLOT!r}; "
                         "restore it before pushing")
    settings = SETTINGS_SCRIPT.read_text(encoding="utf-8")
    return script.replace(SETTINGS_SLOT, f"_SETTINGS_SOURCE: str | None = {settings!r}")


def status(cfg, yes: bool) -> None:
    kernel = f"{cfg.kaggle.username}/{cfg.kaggle.kernel_slug}"
    if not yes:
        print(f"plan: ask Kaggle for the status of the kernel {kernel}")
        print("nothing sent; run again with --yes to ask")
        return
    _run("kernels", "status", kernel)


def fetch(cfg, name: str, force: bool, yes: bool) -> None:
    kernel = f"{cfg.kaggle.username}/{cfg.kaggle.kernel_slug}"
    weights = MODELS_DIR / f"{name}.pt"
    metrics = MODELS_DIR / f"{name}.metrics.json"
    if weights.exists() and not force:
        raise UsageError(f"{weights} already exists; pass --force to replace it")
    if not yes:
        print(f"plan: download the output of the kernel {kernel} "
              f"into {weights} and {metrics}")
        print("nothing downloaded; run again with --yes to fetch")
        return
    with tempfile.TemporaryDirectory(prefix="vision-output-") as tmp:
        _run("kernels", "output", kernel, "-p", tmp)
        for wanted in ("best.pt", "metrics.json"):
            if not (Path(tmp) / wanted).is_file():
                raise UsageError(f"the kernel output has no {wanted}; is the run finished?")
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(tmp) / "best.pt", weights)
        shutil.copyfile(Path(tmp) / "metrics.json", metrics)
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    shown = f"models/{weights.name}"
    print(f"wrote {weights} (sha256 {digest}) and {metrics}")
    print(f"export it: venv\\Scripts\\python scripts\\export_openvino.py --weights {shown}")
    print(f"use the .pt directly, set in config.yaml:  model.weights: {shown}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload, train and fetch on Kaggle.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="is everything in place for Kaggle (local, sends nothing)")
    yes = argparse.ArgumentParser(add_help=False)
    yes.add_argument("--yes", action="store_true",
                     help="really send; without it only the plan is printed")
    upload_cmd = sub.add_parser("upload", parents=[yes], help="upload a build as a private dataset")
    upload_cmd.add_argument("--build", required=True, help="folder name under data/training/build")
    train_cmd = sub.add_parser("train", parents=[yes], help="start training on a Kaggle GPU")
    train_cmd.add_argument("--rough", action="store_true",
                           help="the quick 2-class model: no COCO, rough.epochs")
    sub.add_parser("status", parents=[yes], help="show the training kernel's state")
    fetch_cmd = sub.add_parser("fetch", parents=[yes], help="bring best.pt home as models/N.pt")
    fetch_cmd.add_argument("--name", required=True, help="model name: models/<name>.pt")
    fetch_cmd.add_argument("--force", action="store_true", help="replace an existing models/<name>.pt")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parse_args(argv)
    try:
        cfg = load_training(TRAINING_CONFIG_PATH)
    except (TrainingConfigError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE

    if args.command == "check":
        problems = check(cfg)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return EXIT_USAGE
        print("ok")
        return 0

    if not cfg.kaggle.username.strip():
        print(NO_USERNAME_MESSAGE, file=sys.stderr)
        return EXIT_USAGE
    if args.yes and KAGGLE_EXE is None:
        print(NO_KAGGLE_MESSAGE, file=sys.stderr)
        return EXIT_USAGE
    try:
        if args.command == "upload":
            upload(cfg, args.build, args.yes)
        elif args.command == "train":
            train(cfg, args.rough, args.yes)
        elif args.command == "status":
            status(cfg, args.yes)
        else:
            fetch(cfg, args.name, args.force, args.yes)
    except UsageError as error:
        print(error, file=sys.stderr)
        return EXIT_USAGE
    except _KaggleFailed as error:
        print(error, file=sys.stderr)
        return EXIT_KAGGLE_FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main())
