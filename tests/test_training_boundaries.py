"""The boundaries of `training/`, read from the source files.

`core/` never imports `training/`: the runtime does not learn that phase 4
exists. And the local, offline steps of `training/` import nothing that talks
to the network; only the modules in `NETWORKED` may. A later module that is
offline needs nothing here -- it is scanned the moment it exists.
"""

from __future__ import annotations

from conftest import PROJECT_ROOT
from test_ui_boundaries import imported_modules, top_package

CORE = PROJECT_ROOT / "core"
TRAINING = PROJECT_ROOT / "training"

# Modules allowed to reach the network (spec, decision 10), relative to training/.
NETWORKED = {"kaggle_run.py", "label_studio.py", "kaggle/train.py"}
NETWORK_PACKAGES = {"socket", "requests", "urllib", "urllib3", "http", "kaggle"}


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


def test_the_scan_catches_a_networked_import(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text("def later():\n    import urllib.request\n", encoding="utf-8")
    assert {top_package(m) for m in imported_modules(sample)} & NETWORK_PACKAGES == {"urllib"}
