"""The boundaries of `training/`, read from the source files.

`core/` never imports `training/`: the runtime does not learn that phase 4
exists. And the local, offline steps of `training/` import nothing that talks
to the network; only the modules in `NETWORKED` may. A later module that is
offline needs nothing here -- it is scanned the moment it exists.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from conftest import PROJECT_ROOT
from test_ui_boundaries import imported_modules, top_package

CORE = PROJECT_ROOT / "core"
TRAINING = PROJECT_ROOT / "training"

# Modules allowed to reach the network (spec, decision 10), relative to training/.
NETWORKED = {"kaggle_run.py", "label_studio.py", "kaggle/train.py"}
NETWORK_PACKAGES = {"socket", "requests", "urllib", "urllib3", "http", "kaggle"}

# Offline modules that may import a networked one, for a constant or a function
# that itself stays offline. Importing the module must do nothing on the network:
# `test_importing_the_networked_modules_does_nothing_on_the_network` proves it.
# An entry whose import has since gone away is harmless.
ALLOWED_NETWORKED_IMPORTS = {
    "evaluate.py": {"training.kaggle.train"},  # no_font_download()
    "prelabel.py": {"training.label_studio"},  # IMAGE_NAME, LABEL_NAME
}

# Imports the networked modules at their top level with sockets and subprocesses
# trapped: a pip run or a request on import would be recorded.
IMPORT_CHILD = r"""
import json, socket, subprocess, sys

calls = []


def trap(name):
    def call(*args, **kwargs):
        calls.append(name)
        raise OSError(f"{name} blocked by test")
    return call


socket.getaddrinfo = trap("getaddrinfo")
socket.create_connection = trap("create_connection")
socket.gethostbyname = trap("gethostbyname")
subprocess.Popen = trap("subprocess.Popen")

sys.path.insert(0, sys.argv[1])
import training.kaggle.train
import training.label_studio

print(json.dumps(calls))
"""


def _networked_module_names() -> set[str]:
    return {"training." + name.removesuffix(".py").replace("/", ".") for name in NETWORKED}


def test_core_never_imports_training():
    files = sorted(CORE.glob("*.py"))
    assert files, "core/ has no modules"
    offenders = {
        path.name: sorted(m for m in imported_modules(path) if top_package(m) == "training")
        for path in files
    }
    assert {name: mods for name, mods in offenders.items() if mods} == {}


def test_offline_training_modules_import_nothing_networked():
    files = [path for path in sorted(TRAINING.rglob("*.py"))
             if path.relative_to(TRAINING).as_posix() not in NETWORKED]
    assert files, "training/ has no modules"
    offenders = {
        path.relative_to(TRAINING).as_posix():
            sorted(m for m in imported_modules(path) if top_package(m) in NETWORK_PACKAGES)
        for path in files
    }
    assert {name: mods for name, mods in offenders.items() if mods} == {}


def test_offline_modules_import_only_the_named_networked_modules():
    networked = _networked_module_names()
    files = [path for path in sorted(TRAINING.rglob("*.py"))
             if path.relative_to(TRAINING).as_posix() not in NETWORKED]
    offenders = {}
    for path in files:
        name = path.relative_to(TRAINING).as_posix()
        reached = {m for m in imported_modules(path)
                   if any(m == n or m.startswith(n + ".") for n in networked)}
        extra = reached - ALLOWED_NETWORKED_IMPORTS.get(name, set())
        if extra:
            offenders[name] = sorted(extra)
    assert offenders == {}


def test_importing_the_networked_modules_does_nothing_on_the_network():
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    done = subprocess.run(
        [sys.executable, "-c", IMPORT_CHILD, str(PROJECT_ROOT)],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.strip().splitlines()[-1]) == []


def test_the_scan_catches_a_networked_import(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text("def later():\n    import urllib.request\n", encoding="utf-8")
    assert {top_package(m) for m in imported_modules(sample)} & NETWORK_PACKAGES == {"urllib"}
