"""The order of the trained model's class names, decided in one place.

IDs 0..N-1 are the current model's names in its own order, the new classes
follow. So `config.yaml classes`, `rules.yaml` and `handlers.py` stay valid
for a fine-tuned model: every name it already knew keeps its ID.
"""

from __future__ import annotations


def class_names(base_names: dict[int, str], custom: list[str]) -> list[str]:
    """Base names by ID, then `custom`; `ValueError` on a clash or a gap in the IDs."""
    ids = sorted(base_names)
    if ids != list(range(len(ids))):
        raise ValueError(f"model class IDs are not 0..{len(ids) - 1}: {ids}")
    base = [base_names[index] for index in ids]
    clashes = [name for name in custom if name in base]
    if clashes:
        raise ValueError(f"new class names the model already has: {', '.join(clashes)}")
    return base + list(custom)
