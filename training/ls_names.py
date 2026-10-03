"""The one rule for reading a frame's name back out of a Label Studio export.

`extract_frames` names a frame `<video stem>_<frame index>`. Label Studio may put
a prefix in front of that name in its YOLO export: `<8 hex digits>-` on an
uploaded file, `<task id>-` or `<task id>__` otherwise. `prelabel` (which frames
are labelled already) and `build_dataset` (which video a frame belongs to, and
which exported images are one frame twice) both read exported names through
`frame_name`, so they can never disagree. Names of frames on disk are never put
through it: they carry no prefix.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from pathlib import Path

from core.source import IMAGE_EXTENSIONS

# A prefix is stripped only when what follows still looks like a frame name, so
# `big-pen_000020` (a video called big-pen) stays as it is.
_PREFIX = re.compile(r"^(?:[0-9a-f]{8}-|\d+-|\d+__)(?=.+_\d+$)")


def frame_name(ls_stem: str, frames: Collection[str] = ()) -> str:
    """The frame name (`<video>_<index>`) behind a stem from a Label Studio export.

    `frames` are the names of the frames on disk (`data/training/frames`). An
    exact match wins: `20261003-desk_000020` of a clip called `20261003-desk` is
    not `desk_000020` behind a prefix. A prefix comes off only when what is left
    is a frame on disk; a stem matching neither is returned as it is.

    With no frames on disk to check against (`frames` empty: the folder is gone,
    or the export came from elsewhere) the prefix pattern alone decides, and a
    clip whose name starts with digits and a dash (a date) is misread: keep the
    frames under `data/training/frames` while building.
    """
    if not frames:
        return _PREFIX.sub("", ls_stem, count=1)
    if ls_stem in frames:
        return ls_stem
    stripped = _PREFIX.sub("", ls_stem, count=1)
    return stripped if stripped in frames else ls_stem


def maybe_dated(ls_stem: str) -> bool:
    """True when the `<digits>-` in front could be a task id or the start of a clip's name.

    Only the frames on disk tell the two apart; without them `frame_name` takes
    it for a prefix, and the caller warns.
    """
    return _DIGITS_DASH.match(ls_stem) is not None


_DIGITS_DASH = re.compile(r"^\d+-(?=.+_\d+$)")


def disk_frames(root: Path) -> set[str]:
    """Names (stems) of every image under `root`, the frames `frame_name` checks against."""
    if not root.is_dir():
        return set()
    return {path.stem for path in root.rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS}
