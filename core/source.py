"""Turning whatever the user pointed at into a stream of frames.

One interface over every input: a single image, a folder of images, a video
file and a webcam. Everything downstream is written against the iterator of
`Frame`s alone and never learns which of them is in use. RTSP is not
implemented; adding it later changes this module and nothing below it.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
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
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v")

# `--source camera:N`; a bare whole number that is not an existing path means
# the same thing.
CAMERA_PREFIX = "camera:"

# DirectShow opens in well under a second on Windows; the default Media
# Foundation backend can take ten and sometimes never reports a missing camera
# as missing. Elsewhere OpenCV's own choice is the right one.
CAMERA_BACKEND = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY

# A camera index nobody is plugged into makes the backend log a warning of its
# own before returning a closed capture, and a damaged video file does the
# same. The sentence this module raises says the same thing in one line, and
# two messages for one problem read like two problems.
cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)


class Source:
    """An iterable of `Frame`s over an image, a folder, a video or a webcam.

    `is_stream` is True for a video file and a webcam; `is_camera` for a webcam
    only. `fps` is the rate the container or camera reports, and 0 for stills.
    `frame_size` is the actual `(w, h)` of a stream's frames and None for stills.

    A webcam is held from the constructor on, so the source is a context
    manager: `close()` (or leaving the `with` block) releases the camera on
    every path out, rather than whenever the garbage collector gets to it. It
    is idempotent, and does nothing for stills and video files, which hold
    nothing between iterations.
    """

    def __init__(self, spec: str | Path, cfg: Config) -> None:
        # `cfg` carries the capture resolution the webcam asks for.
        self._cfg = cfg
        self._path = Path(spec)
        self._paths: list[Path] = []
        self._video: Path | None = None
        self._frame_count = 0
        self._camera: int | None = None
        self._capture: cv2.VideoCapture | None = None
        self.is_stream = False
        self.is_camera = False
        self.fps = 0.0
        self.frame_size: tuple[int, int] | None = None

        camera = _camera_index(spec)
        if camera is not None:
            self._start_camera(camera)
        elif self._path.is_file() and _is_video(self._path):
            self._probe_video()
        else:
            self._paths = self._resolve()

    def __enter__(self) -> Source:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    def close(self) -> None:
        """Release the camera now. Safe to call again, and on any source."""
        capture, self._capture = self._capture, None
        if capture is not None:
            capture.release()
            log.debug("camera %d released", self._camera)

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
            raise ValueError(f"not an image or video: {self._path}")
        return [self._path]

    def _probe_video(self) -> None:
        """Open the file once, read its first frame, and remember what it said.

        Done here rather than on first iteration so that a file that will not
        play fails before the model loads, as one sentence.
        """
        capture = _open_video(self._path)
        try:
            ok, image = capture.read()
            if not ok or image is None:
                raise ValueError(f"cannot open video: {self._path}")
            self.fps = max(0.0, float(capture.get(cv2.CAP_PROP_FPS)))
            self._frame_count = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        finally:
            capture.release()
        self._video = self._path
        self.is_stream = True
        self.frame_size = (image.shape[1], image.shape[0])

    def _start_camera(self, index: int) -> None:
        """Open the camera now, so a missing one fails before the model loads."""
        capture = open_camera(index, self._cfg)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        wanted = (self._cfg.capture.width, self._cfg.capture.height)
        if (width, height) != wanted:
            log.warning(
                "camera %d delivers %dx%d, not the requested %dx%d",
                index, width, height, *wanted,
            )
        self._camera = index
        self._capture = capture
        self.is_stream = True
        self.is_camera = True
        self.fps = max(0.0, float(capture.get(cv2.CAP_PROP_FPS)))
        self.frame_size = (width, height)

    def __len__(self) -> int:
        """Frames this source will yield.

        The container's count for a video, and 0 for a webcam, which means
        "unknown" -- a camera runs until it is stopped.
        """
        if self._camera is not None:
            return 0
        if self._video is not None:
            return self._frame_count
        return len(self._paths)

    def __iter__(self) -> Iterator[Frame]:
        if self._camera is not None:
            yield from self._iter_camera()
            return
        if self._video is not None:
            yield from self._iter_video()
            return
        for index, path in enumerate(self._paths):
            log.debug("reading frame %d from %s", index, path)
            yield Frame(image=_read(path), source=str(path), index=index)

    def _iter_video(self) -> Iterator[Frame]:
        capture = _open_video(self._video)
        try:
            index = 0
            while True:
                ok, image = capture.read()
                if not ok or image is None:
                    return
                if self.fps > 0:
                    stamp = index / self.fps
                else:
                    stamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                yield Frame(image=image, source=str(self._video), index=index, time=stamp)
                index += 1
        finally:
            capture.release()

    def _iter_camera(self) -> Iterator[Frame]:
        """Frames until the caller stops; the camera is released either way.

        The capture was opened in the constructor and is used once: a second
        iteration, or one after `close()`, is a `RuntimeError` -- the camera
        itself did nothing wrong, so it is not reported as stopped.
        """
        capture = self._capture
        if capture is None:
            raise RuntimeError(f"source already consumed: camera {self._camera}")
        source = f"{CAMERA_PREFIX}{self._camera}"
        try:
            start = None
            index = 0
            while True:
                if self._capture is None:
                    return  # closed by the owner between two frames
                ok, image = capture.read()
                if not ok or image is None:
                    raise OSError(f"camera {self._camera} stopped delivering frames")
                now = time.monotonic()
                if start is None:
                    start = now
                yield Frame(image=image, source=source, index=index, time=now - start)
                index += 1
        finally:
            self.close()


def open_camera(index: int, cfg: Config) -> cv2.VideoCapture:
    """Open one camera at the configured resolution.

    Raises `OSError` naming the index when the camera is missing or held by
    another program -- the two cases look identical from here, and the sentence
    says so rather than guessing. The driver keeps a single frame, so a slow
    consumer reads the newest picture rather than a queue of old ones.
    """
    capture = cv2.VideoCapture(index, CAMERA_BACKEND)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.capture.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.capture.height)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not capture.isOpened():
        capture.release()
        raise OSError(f"camera {index} is not available or busy")
    return capture


def is_stream_spec(spec: str | Path) -> bool:
    """Whether `Source(spec, cfg)` would be a stream, decided without opening it.

    True for `camera:N` (or a bare index) and for an existing video file. Lets
    a caller check what only a stream needs before a camera is switched on.
    Raises `ValueError` for a `camera:` prefix without a whole number, as the
    constructor would.
    """
    if _camera_index(spec) is not None:
        return True
    path = Path(spec)
    return path.is_file() and _is_video(path)


def _camera_index(spec: str | Path) -> int | None:
    """The camera a spec names, or None when it names a path.

    `camera:N`, or a bare whole number that is not an existing path. A
    `camera:` prefix with anything but a whole number after it is refused.
    """
    if isinstance(spec, Path):
        return None
    text = spec.strip()
    if text.lower().startswith(CAMERA_PREFIX):
        number = text[len(CAMERA_PREFIX):]
        if not _is_whole(number):
            raise ValueError(f"not a camera index: {spec} (expected {CAMERA_PREFIX}N)")
        return int(number)
    if _is_whole(text) and not Path(text).exists():
        return int(text)
    return None


def _is_whole(text: str) -> bool:
    return text.isascii() and text.isdigit()


def _is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _open_video(path: Path) -> cv2.VideoCapture:
    """Open a video file, raising `ValueError` when OpenCV cannot.

    Some `VideoCapture` backends take the name as a narrow string on Windows
    and cannot open a path outside the system code page. Such a path is
    handed over as its 8.3 short name, which is plain ASCII. The FFmpeg
    backend copes with the long name too, so a volume without short names
    only fails if the long name does not open either.
    """
    text = str(path)
    narrow = _short_path(text) if not _fits_code_page(text) else text
    capture = cv2.VideoCapture(narrow or text)
    if not capture.isOpened() and narrow and narrow != text:
        capture.release()
        capture = cv2.VideoCapture(text)
    if not capture.isOpened():
        capture.release()
        if narrow is None:
            raise ValueError(f"cannot open video: {path} (rename it to ASCII)")
        raise ValueError(f"cannot open video: {path}")
    return capture


def _fits_code_page(text: str) -> bool:
    """Whether `text` survives the narrow-string conversion Windows applies."""
    if sys.platform != "win32":
        return True
    try:
        text.encode(f"cp{ctypes.windll.kernel32.GetACP()}")
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _short_path(text: str) -> str | None:
    """The 8.3 short form of an existing path, or None when the volume has none."""
    get_short = ctypes.windll.kernel32.GetShortPathNameW
    size = get_short(text, None, 0)
    if not size:
        return None
    buffer = ctypes.create_unicode_buffer(size)
    if not get_short(text, buffer, size):
        return None
    short = buffer.value
    # With short names disabled the call succeeds and returns the long name.
    return short if _fits_code_page(short) else None


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
