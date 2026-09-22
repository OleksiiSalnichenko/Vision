"""The output seam: what a stream and a photo leave in `output.dir` and print.

Everything is written into `tmp_path`; no model is loaded. The expected shapes
come from the phase-2 spec (stories 35, 41-45) and the JSON contract of phase 1,
listed here by hand.
"""

from __future__ import annotations

import json
from dataclasses import replace

import cv2
import numpy as np
import pytest

from core import output
from core.config import load_config
from core.target import TargetState
from core.types import Detection, Frame

WIDTH, HEIGHT = 64, 48

# The phase-1 detection keys, in order, from the JSON contract.
PHOTO_KEYS = [
    "cls_id", "cls_name", "conf", "bbox", "center",
    "dx", "dy", "dx_pct", "dy_pct", "color", "debug",
]


@pytest.fixture
def out_dir(tmp_path):
    return tmp_path / "out"


@pytest.fixture
def cfg(write_config, out_dir):
    return load_config(
        write_config(
            {"output.dir": str(out_dir), "output.save_json": True, "output.save_image": True}
        )
    )


def _detection(track_id=None, conf=0.83, dx=12, dy=-4) -> Detection:
    return Detection(
        cls_id=0,
        cls_name="person",
        conf=conf,
        bbox=(10.0, 8.0, 30.0, 40.0),
        center=(20, 24),
        dx=dx,
        dy=dy,
        dx_pct=0.375,
        dy_pct=-0.1667,
        track_id=track_id,
    )


def _frame(index: int, source: str = "clip.mp4", time: float = 0.0) -> Frame:
    image = np.full((HEIGHT, WIDTH, 3), (index * 20) % 256, dtype=np.uint8)
    return Frame(image=image, source=source, index=index, time=time)


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_the_jsonl_has_one_line_per_write(cfg, out_dir):
    drawn = [_detection(track_id=7)]
    near = [_detection(track_id=None, conf=0.31)]

    with output.StreamWriter("clip.mp4", cfg, 25.0, (WIDTH, HEIGHT), video=False) as writer:
        for index in range(3):
            frame = _frame(index, time=index / 3)
            writer.write(frame, drawn, near, None, frame.image)

    lines = _lines(out_dir / "clip.jsonl")
    assert len(lines) == 3
    assert [line["index"] for line in lines] == [0, 1, 2]
    assert lines[1]["time"] == 0.333
    assert lines[0]["source"] == "clip.mp4"
    assert lines[0]["target"] is None
    first, second = lines[0]["detections"]
    assert (first["track_id"], first["debug"]) == (7, False)
    assert (second["track_id"], second["debug"]) == (None, True)


def test_the_target_is_written_as_id_lock_and_loss(cfg, out_dir):
    target = _detection(track_id=7)
    states = [
        TargetState(target, locked=True, lost=False),
        TargetState(None, locked=True, lost=True),
        TargetState(None, locked=False, lost=False),
    ]

    with output.StreamWriter("clip.mp4", cfg, 25.0, (WIDTH, HEIGHT), video=False) as writer:
        for index, state in enumerate(states):
            frame = _frame(index)
            writer.write(frame, [target], [], state, frame.image)

    lines = _lines(out_dir / "clip.jsonl")
    assert lines[0]["target"] == {"track_id": 7, "locked": True, "lost": False}
    assert lines[1]["target"] == {"track_id": None, "locked": True, "lost": True}
    assert lines[2]["target"] is None


def test_the_camera_stem_has_no_colon(cfg, out_dir):
    with output.StreamWriter("camera:0", cfg, 30.0, (WIDTH, HEIGHT), video=False) as writer:
        writer.write(_frame(0, source="camera:0"), [], [], None, _frame(0).image)

    assert (out_dir / "camera_0.jsonl").is_file()


def test_save_json_false_writes_no_jsonl(cfg, out_dir):
    cfg = replace(cfg, output=replace(cfg.output, save_json=False))

    with output.StreamWriter("clip.mp4", cfg, 25.0, (WIDTH, HEIGHT), video=False) as writer:
        writer.write(_frame(0), [], [], None, _frame(0).image)

    assert not (out_dir / "clip.jsonl").exists()


def _frames_in(path) -> int:
    capture = cv2.VideoCapture(str(path))
    try:
        count = 0
        while capture.read()[0]:
            count += 1
        return count
    finally:
        capture.release()


def test_a_video_file_gets_an_mp4_with_every_frame(cfg, out_dir):
    with output.StreamWriter("clip.mp4", cfg, 10.0, (WIDTH, HEIGHT), video=True) as writer:
        for index in range(5):
            frame = _frame(index)
            writer.write(frame, [], [], None, frame.image)
    paths = writer.close()

    video = out_dir / "clip_annotated.mp4"
    assert video in paths and out_dir / "clip.jsonl" in paths
    assert _frames_in(video) == 5
    assert not list(out_dir.glob("*.part.mp4"))


def test_a_cyrillic_stem_ends_up_under_its_own_name(cfg, out_dir):
    with output.StreamWriter("відео.mp4", cfg, 10.0, (WIDTH, HEIGHT), video=True) as writer:
        for index in range(3):
            frame = _frame(index, source="відео.mp4")
            writer.write(frame, [], [], None, frame.image)

    video = out_dir / "відео_annotated.mp4"
    assert video.is_file() and video.stat().st_size > 0
    assert (out_dir / "відео.jsonl").is_file()
    assert not list(out_dir.glob("*.part.mp4"))


def test_an_exception_mid_stream_still_leaves_closed_files(cfg, out_dir):
    with pytest.raises(KeyboardInterrupt):
        with output.StreamWriter("clip.mp4", cfg, 10.0, (WIDTH, HEIGHT), video=True) as writer:
            for index in range(2):
                frame = _frame(index)
                writer.write(frame, [_detection(track_id=3)], [], None, frame.image)
            raise KeyboardInterrupt

    assert len(_lines(out_dir / "clip.jsonl")) == 2
    assert _frames_in(out_dir / "clip_annotated.mp4") == 2
    assert writer.close() == writer.close()


def test_a_wrong_size_frame_is_refused_before_anything_is_written(cfg, out_dir):
    wrong = np.zeros((HEIGHT + 2, WIDTH, 3), dtype=np.uint8)

    with output.StreamWriter("clip.mp4", cfg, 10.0, (WIDTH, HEIGHT), video=True) as writer:
        writer.write(_frame(0), [], [], None, _frame(0).image)
        with pytest.raises(ValueError):
            writer.write(_frame(1), [], [], None, wrong)

    assert len(_lines(out_dir / "clip.jsonl")) == 1
    assert _frames_in(out_dir / "clip_annotated.mp4") == 1


def test_a_camera_gets_no_video(cfg, out_dir):
    with output.StreamWriter("camera:0", cfg, 30.0, (WIDTH, HEIGHT), video=False) as writer:
        writer.write(_frame(0, source="camera:0"), [], [], None, _frame(0).image)

    assert not list(out_dir.glob("*.mp4"))


def _event(time=12.4, track_id=7):
    # Duck-typed stand-in with the attributes of core.rules.Event.
    from types import SimpleNamespace

    return SimpleNamespace(
        rule="person_appeared",
        when="appeared",
        detection=_detection(track_id=track_id, conf=0.83, dx=120, dy=-40),
        time=time,
        actions=("log",),
    )


@pytest.mark.parametrize(
    "time, clock", [(12.4, "00:12.4"), (75.0, "01:15.0"), (59.96, "01:00.0")]
)
def test_an_event_prints_as_one_line(capsys, time, clock):
    output.print_event(_event(time=time))

    assert capsys.readouterr().out == (
        f"[{clock}] person_appeared  person #7 0.83  dx +120 dy -40\n"
    )


def test_an_event_frame_goes_under_events(cfg, out_dir):
    image = _frame(1).image

    path = output.write_event_frame(_event(), "clip.mp4", 42, image, cfg)

    assert path == out_dir / "events" / "clip_person_appeared_42.jpg"
    decoded = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == image.shape


def test_the_stream_summary_names_what_was_written(capsys, tmp_path):
    output.print_stream_summary(120, 3, [tmp_path / "a.jsonl", tmp_path / "b.mp4"])
    output.print_stream_summary(0, 0, [])

    first, second = capsys.readouterr().out.splitlines()
    assert first == f"120 frames, 3 events, wrote {tmp_path / 'a.jsonl'}, {tmp_path / 'b.mp4'}"
    assert second == "0 frames, 0 events, wrote nothing"


def test_the_photo_json_keeps_its_phase_1_shape(cfg, out_dir):
    path = output.write_json("bus.jpg", [_detection(track_id=7)], cfg)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert list(payload) == ["source", "detections"]
    assert list(payload["detections"][0]) == PHOTO_KEYS
