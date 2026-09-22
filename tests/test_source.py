"""`core.source.Source` over video files -- seam 4 of the phase-2 spec.

Each test writes its own tiny clip into `tmp_path`, so nothing here depends on
a file in the repository, and no test ever opens a camera.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

import core.source
from core.config import load_config
from core.source import Source

FRAMES = 10
WIDTH, HEIGHT = 64, 48
FPS = 10.0


@pytest.fixture
def cfg(write_config):
    return load_config(write_config())


def _write_clip(path: Path) -> Path:
    """Write a 10-frame 64x48 mp4v clip at 10 fps to an ASCII path."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    assert writer.isOpened(), "OpenCV cannot write mp4v here"
    for shade in range(FRAMES):
        writer.write(np.full((HEIGHT, WIDTH, 3), shade * 20, dtype=np.uint8))
    writer.release()
    return path


@pytest.fixture
def clip(tmp_path) -> Path:
    return _write_clip(tmp_path / "clip.mp4")


def test_video_yields_every_frame_in_order(clip, cfg):
    frames = list(Source(clip, cfg))

    assert [frame.index for frame in frames] == list(range(FRAMES))
    assert all(frame.image.shape == (HEIGHT, WIDTH, 3) for frame in frames)


def test_video_time_is_index_over_fps(clip, cfg):
    frames = list(Source(clip, cfg))

    # 10 fps: frame n sits n tenths of a second into the clip.
    assert [frame.time for frame in frames] == pytest.approx([n / 10 for n in range(FRAMES)])
    assert all(frame.source == str(clip) for frame in frames)


def test_video_is_a_stream_with_its_size_rate_and_length(clip, cfg):
    source = Source(clip, cfg)

    assert source.is_stream is True
    assert source.frame_size == (WIDTH, HEIGHT)
    assert source.fps == pytest.approx(FPS)
    assert len(source) == FRAMES


def test_still_image_is_not_a_stream(tmp_path, cfg):
    ok, buffer = cv2.imencode(".png", np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8))
    assert ok
    image = tmp_path / "still.png"
    image.write_bytes(buffer.tobytes())

    source = Source(image, cfg)
    frames = list(source)

    assert (source.is_stream, source.fps, source.frame_size, len(source)) == (False, 0, None, 1)
    assert (frames[0].index, frames[0].time) == (0, 0.0)


def test_video_under_a_cyrillic_name_opens(tmp_path, cfg):
    # VideoWriter goes through a narrow string too, so write under ASCII first.
    folder = tmp_path / "тест"
    folder.mkdir()
    clip = _write_clip(tmp_path / "clip.mp4").replace(folder / "відео.mp4")

    try:
        source = Source(clip, cfg)
    except ValueError as err:
        if "rename it to ASCII" in str(err):
            pytest.skip("this volume has no 8.3 short names, so a non-ANSI path cannot open")
        raise

    frames = list(source)
    assert len(frames) == FRAMES
    assert frames[0].source == str(clip)


def test_missing_video_is_not_found(tmp_path, cfg):
    with pytest.raises(FileNotFoundError, match="source not found"):
        Source(tmp_path / "absent.mp4", cfg)


@pytest.mark.parametrize("content", [b"this is not a video at all\n", b""], ids=["text", "empty"])
def test_broken_video_fails_in_the_constructor(tmp_path, cfg, content):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(content)

    with pytest.raises(ValueError, match="cannot open video: "):
        Source(broken, cfg)


@pytest.mark.parametrize("spec", ["camera:", "camera:x", "camera:-1"])
def test_camera_without_an_index_is_refused(cfg, spec):
    with pytest.raises(ValueError, match="camera"):
        Source(spec, cfg)


# --- releasing the camera ----------------------------------------------------
#
# The camera is a stand-in: `open_camera` is replaced before `Source` is built,
# so these tests never reach a driver. Index 9 is one nobody has plugged in,
# should a regression bypass the stand-in.


class FakeCapture:
    """A camera that delivers black frames until it is released."""

    def __init__(self, width: int, height: int) -> None:
        self.size = (width, height)
        self.releases = 0

    def get(self, prop):
        return {
            cv2.CAP_PROP_FRAME_WIDTH: self.size[0],
            cv2.CAP_PROP_FRAME_HEIGHT: self.size[1],
            cv2.CAP_PROP_FPS: 30.0,
        }.get(prop, 0.0)

    def read(self):
        if self.releases:
            return False, None
        return True, np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)

    def release(self) -> None:
        self.releases += 1


@pytest.fixture
def camera(monkeypatch, cfg):
    """The capture `Source("camera:9", cfg)` will be handed."""
    capture = FakeCapture(cfg.capture.width, cfg.capture.height)

    def fake_open(index, _cfg):
        assert index == 9
        return capture

    monkeypatch.setattr(core.source, "open_camera", fake_open)
    return capture


def test_close_releases_the_camera_exactly_once(camera, cfg):
    source = Source("camera:9", cfg)

    source.close()
    source.close()

    assert camera.releases == 1


def test_leaving_a_with_block_releases_the_camera(camera, cfg):
    with Source("camera:9", cfg) as source:
        assert source.is_camera
    assert camera.releases == 1


def test_a_closed_camera_cannot_be_iterated_again(camera, cfg):
    source = Source("camera:9", cfg)
    source.close()

    with pytest.raises(RuntimeError, match="^source already consumed: camera 9$"):
        next(iter(source))


def test_a_camera_is_consumed_by_its_first_iteration(camera, cfg):
    source = Source("camera:9", cfg)
    frames = iter(source)
    next(frames)
    next(frames)
    frames.close()  # the caller stopped: the camera is released

    with pytest.raises(RuntimeError, match="^source already consumed: camera 9$"):
        next(iter(source))
    assert camera.releases == 1


def test_close_on_a_still_changes_nothing(tmp_path, cfg):
    path = tmp_path / "still.jpg"
    ok, encoded = cv2.imencode(".jpg", np.zeros((8, 8, 3), dtype=np.uint8))
    path.write_bytes(encoded.tobytes())
    source = Source(path, cfg)

    source.close()

    assert not source.is_camera
    assert len(list(source)) == 1
