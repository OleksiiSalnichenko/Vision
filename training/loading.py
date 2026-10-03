"""Loading a model for a `training/` command: one sentence when the weights are broken."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def load_model(make: Callable[[], T], weights: str | Path) -> T:
    """`make()`, or a one-line `ValueError` naming `weights`.

    Broken weights raise anything at all from torch or OpenVINO (RuntimeError,
    KeyError, pickle errors, ...), often over several lines; a command prints
    one sentence instead of a traceback.
    """
    try:
        return make()
    except Exception as error:  # noqa: BLE001 -- see the docstring
        lines = str(error).strip().splitlines() or [type(error).__name__]
        raise ValueError(f"cannot load the model {weights}: {lines[0]}") from None
