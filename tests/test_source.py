"""`core.source.Source` over video files -- seam 4 of the phase-2 spec.

Each test writes its own tiny clip into `tmp_path`, so nothing here depends on
a file in the repository, and no test ever opens a camera.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

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
