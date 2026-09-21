"""Turning whatever the user pointed at into a stream of frames.

One interface over every input. Phase 1 implements two of them -- a single
image and a folder of images -- and everything downstream is written against
the iterator alone, so adding video, a webcam index or an RTSP URL later
changes this module and nothing below it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

from core.config import Config
from core.types import Frame

log = logging.getLogger(__name__)

# Extensions OpenCV decodes without extra plugins. Names, not tunables: a new
# format here is a code change, not a knob the user turns in config.yaml.
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff")


class Source:
    """An iterable of `Frame`s over a single image or a folder of images."""

    def __init__(self, spec: str | Path, cfg: Config) -> None:
        # `cfg` carries the capture resolution, which only the webcam and RTSP
        # inputs of phase 2 will read. It is taken now so that adding them does
        # not change this signature or any caller.
        self._cfg = cfg
        self._path = Path(spec)
        self._paths = self._resolve()

    def _resolve(self) -> list[Path]:
        """List the images this source will yield, in the order it yields them."""
        if self._path.is_dir():
            images = sorted(
                (child for child in self._path.iterdir() if _is_image(child)),
                key=lambda child: child.name.lower(),
            )
            if not images:
                raise FileNotFoundError(f"no images in folder: {self._path}")
            return images

        if not self._path.exists():
            raise FileNotFoundError(f"source not found: {self._path}")
        if not _is_image(self._path):
            raise ValueError(f"not an image: {self._path}")
        return [self._path]

    def __len__(self) -> int:
        return len(self._paths)

    def __iter__(self) -> Iterator[Frame]:
        for index, path in enumerate(self._paths):
            log.debug("reading frame %d from %s", index, path)
            yield Frame(image=_read(path), source=str(path), index=index)


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _read(path: Path) -> np.ndarray:
    """Decode one image file into a BGR array.

    Read as bytes and decoded in memory rather than through `cv2.imread`:
    imread goes through a narrow-string path on Windows and silently returns
    None for any folder or file name outside the system code page.
    """
    buffer = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR) if buffer.size else None
    if image is None:
        raise ValueError(f"cannot decode image: {path}")
    return image
