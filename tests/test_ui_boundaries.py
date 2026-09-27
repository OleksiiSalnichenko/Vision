"""The boundaries between `core/` and the desktop app, read from the source files.

`core/` must never learn that a window exists: `ui/` imports `core/`, never the
reverse. And every string the app shows or logs is English, so no Cyrillic
character may sit anywhere in `ui/` or `app.py`. Both are checked on the text
of the files, so nothing has to be imported (and no Qt started) to check them.
"""

import ast
import re
from pathlib import Path

from conftest import PROJECT_ROOT

CORE = PROJECT_ROOT / "core"
UI = PROJECT_ROOT / "ui"
FORBIDDEN_IN_CORE = ("PySide6", "ui", "shiboken6")
CYRILLIC = re.compile("[Ѐ-ӿԀ-ԯ]")


def imported_modules(path: Path) -> set[str]:
    """Every module `path` imports, anywhere in the file (lazy imports included)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def top_package(module: str) -> str:
    return module.split(".")[0]


def test_imported_modules_sees_lazy_and_from_imports(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        "import os\n"
        "from PySide6.QtCore import Qt\n"
        "def later():\n"
        "    import ui.worker\n",
        encoding="utf-8",
    )
    assert imported_modules(sample) == {"os", "PySide6.QtCore", "ui.worker"}


def test_core_never_imports_qt_or_ui():
    files = sorted(CORE.glob("*.py"))
    assert files, "core/ has no modules"
    offenders = {
        path.name: sorted(m for m in imported_modules(path)
                          if top_package(m) in FORBIDDEN_IN_CORE)
        for path in files
    }
    assert {name: mods for name, mods in offenders.items() if mods} == {}


def test_the_app_has_no_cyrillic_anywhere():
    files = sorted(UI.glob("*.py")) + [PROJECT_ROOT / "app.py"]
    assert len(files) > 1, "ui/ has no modules"
    found = {}
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CYRILLIC.search(line):
                found[f"{path.relative_to(PROJECT_ROOT)}:{number}"] = line.strip()
    assert found == {}


def test_the_cyrillic_pattern_catches_ukrainian():
    assert CYRILLIC.search("Відкрити файл")
    assert CYRILLIC.search("ї є ґ")
    assert not CYRILLIC.search("Open file… ◀ Prev Next ▶ — fixed by the export")
