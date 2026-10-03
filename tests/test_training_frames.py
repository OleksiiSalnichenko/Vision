"""`training/extract_frames.py`: every Nth frame of a video into `data/training/frames`.

A tiny mp4 is written into `tmp_path`; the frames root and the training config
are pointed into `tmp_path` too, so nothing under `data/` is touched.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from test_training_settings import training_text
from training import extract_frames

FRAMES = 10
WIDTH, HEIGHT = 64, 48


def _write_clip(path: Path) -> Path:
    """A 10-frame clip whose frame i is filled with grey level i * 20."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (WIDTH, HEIGHT))
    assert writer.isOpened(), "OpenCV cannot write mp4v here"
    for shade in range(FRAMES):
        writer.write(np.full((HEIGHT, WIDTH, 3), shade * 20, dtype=np.uint8))
    writer.release()
    return path


@pytest.fixture
def frames_root(tmp_path, monkeypatch):
    root = tmp_path / "frames"
    monkeypatch.setattr(extract_frames, "FRAMES_ROOT", root)
    return root


@pytest.fixture
def training_config(tmp_path, monkeypatch):
    path = tmp_path / "training.yaml"
    path.write_text(training_text({"frames.step": 3, "frames.target_total": 50}), encoding="utf-8")
    monkeypatch.setattr(extract_frames, "TRAINING_CONFIG_PATH", path)
    return path


def _grey(path: Path) -> float:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    return float(image.mean())


def test_extract_keeps_every_nth_frame_under_its_index(tmp_path):
    clip = _write_clip(tmp_path / "desk.mp4")
    out = tmp_path / "out"

    written = extract_frames.extract(clip, out, 3)

    assert written == 4
    names = sorted(path.name for path in out.iterdir())
    assert names == ["desk_000000.jpg", "desk_000003.jpg", "desk_000006.jpg", "desk_000009.jpg"]
    # The frame stored as 000006 is the seventh one: grey level 6 * 20.
    assert abs(_grey(out / "desk_000006.jpg") - 120) < 8


def test_main_writes_into_frames_root_and_reports_totals(
        tmp_path, frames_root, training_config, capsys):
    clip = _write_clip(tmp_path / "desk.mp4")
    (frames_root / "older").mkdir(parents=True)
    for index in range(5):
        (frames_root / "older" / f"older_{index:06d}.jpg").write_bytes(b"x")

    assert extract_frames.main(["--video", str(clip)]) == 0

    out = frames_root / "desk"
    assert len(list(out.glob("desk_*.jpg"))) == 4
    printed = capsys.readouterr().out
    assert f"wrote 4 frames to {out}" in printed
    assert "total 9 frames in" in printed
    assert "(target ~50)" in printed


def test_a_cyrillic_video_name_and_folder_work(tmp_path, frames_root, training_config, capsys):
    folder = tmp_path / "відео"
    folder.mkdir()
    clip = _write_clip(tmp_path / "clip.mp4").replace(folder / "ручка.mp4")

    code = extract_frames.main(["--video", str(clip), "--out", str(tmp_path / "кадри")])
    if code == 2 and "rename it to ASCII" in capsys.readouterr().err:
        pytest.skip("this volume has no 8.3 short names, so a non-ANSI path cannot open")

    assert code == 0
    written = sorted((tmp_path / "кадри").iterdir())
    assert [path.name for path in written][0] == "ручка_000000.jpg"
    assert len(written) == 4


def test_a_folder_with_files_is_refused_without_force(
        tmp_path, frames_root, training_config, capsys):
    clip = _write_clip(tmp_path / "desk.mp4")
    out = frames_root / "desk"
    out.mkdir(parents=True)
    (out / "keep.txt").write_text("mine", encoding="utf-8")

    assert extract_frames.main(["--video", str(clip)]) == 2
    err = capsys.readouterr().err
    assert "--force" in err and str(out) in err
    assert err.count("\n") == 1 and "Traceback" not in err
    assert sorted(path.name for path in out.iterdir()) == ["keep.txt"]


def test_force_writes_into_a_folder_with_files(tmp_path, frames_root, training_config):
    clip = _write_clip(tmp_path / "desk.mp4")
    out = frames_root / "desk"
    out.mkdir(parents=True)
    (out / "desk_000000.jpg").write_bytes(b"old")

    assert extract_frames.main(["--video", str(clip), "--force"]) == 0
    assert len(list(out.glob("desk_*.jpg"))) == 4
    assert (out / "desk_000000.jpg").read_bytes() != b"old"


def test_a_missing_video_is_one_sentence(tmp_path, frames_root, training_config, capsys):
    missing = tmp_path / "nope.mp4"
    assert extract_frames.main(["--video", str(missing)]) == 2
    err = capsys.readouterr().err
    assert str(missing) in err and err.count("\n") == 1 and "Traceback" not in err
    assert not frames_root.exists()


def test_an_image_is_not_a_video(tmp_path, frames_root, training_config, capsys):
    image = tmp_path / "photo.jpg"
    image.write_bytes(cv2.imencode(".jpg", np.zeros((8, 8, 3), np.uint8))[1].tobytes())
    assert extract_frames.main(["--video", str(image)]) == 2
    assert "not a video" in capsys.readouterr().err


def test_a_broken_training_config_is_one_sentence(
        tmp_path, frames_root, training_config, capsys):
    training_config.write_text(training_text(without=("frames.step",)), encoding="utf-8")
    clip = _write_clip(tmp_path / "desk.mp4")
    assert extract_frames.main(["--video", str(clip)]) == 2
    err = capsys.readouterr().err
    assert "frames.step" in err and err.count("\n") == 1
