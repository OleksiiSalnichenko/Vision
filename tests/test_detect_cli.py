"""The wiring `detect.py` owns: the drawn / near-miss split and the two thresholds.

`Detector` hands back one list holding everything from `conf_debug` upwards,
and `detect.py` is the only place that splits it. `core.draw` and `core.output`
are handed ready-made lists and know no threshold at all, so nothing but these
assertions would notice a near-miss starting to be drawn and printed.

No model is loaded here: the detector is a stand-in that returns a fixed list,
which is all `process` asks of it. The thresholds below are the shipped ones
from the spec -- draw and print at `conf` 0.5, keep down to `conf_debug` 0.25.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

import detect
from core import draw, events, output
from core.config import load_config
from core.types import Detection, Frame

CONF = 0.5
CONF_DEBUG = 0.25


@pytest.fixture
def cfg(tmp_path, write_config):
    """The shipped thresholds, with the output written into `tmp_path`."""
    return load_config(
        write_config(
            {
                "model.conf": CONF,
                "model.conf_debug": CONF_DEBUG,
                "output.save_json": True,
                "output.save_image": False,
                "output.dir": tmp_path.as_posix(),
            }
        )
    )


class StubDetector:
    """Stands in for `Detector`: one call, one fixed list, no weights."""

    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def __call__(self, frame: Frame) -> list[Detection]:
        return list(self._detections)


def detection(cls_name: str, conf: float) -> Detection:
    return Detection(
        cls_id=0,
        cls_name=cls_name,
        conf=conf,
        bbox=(10.0, 10.0, 30.0, 30.0),
        center=(20, 20),
        dx=-20,
        dy=-10,
        dx_pct=-0.5,
        dy_pct=-0.33,
    )


def flags(**overrides) -> argparse.Namespace:
    """The parsed command line, with everything not named left unset."""
    return argparse.Namespace(**{"conf": None, "classes": None, **overrides})


def test_only_detections_at_or_above_conf_are_drawn_printed_and_marked(
    cfg, tmp_path, capsys, monkeypatch
):
    # Exactly at the threshold counts as drawn: the spec says "at or above".
    sure = detection("person", CONF)
    near_miss = detection("bottle", 0.30)
    handed_to_annotate = []
    monkeypatch.setattr(
        draw,
        "annotate",
        lambda image, detections, config: handed_to_annotate.append(list(detections))
        or image,
    )
    frame = Frame(image=np.zeros((60, 80, 3), np.uint8), source="photo.jpg", index=0)

    detect.process(frame, StubDetector([sure, near_miss]), cfg, want_color=False)

    printed = capsys.readouterr().out
    assert handed_to_annotate == [[sure]]
    assert "person" in printed
    assert "bottle" not in printed  # a near miss is never drawn and never printed
    written = json.loads(Path(tmp_path / "photo.json").read_text(encoding="utf-8"))
    assert [(item["cls_name"], item["debug"]) for item in written["detections"]] == [
        ("person", False),
        ("bottle", True),
    ]


def test_conf_flag_below_conf_debug_lowers_the_lower_threshold_too(cfg):
    # The model runs one pass at conf_debug, so a flag under that floor would
    # otherwise show exactly what conf_debug already showed.
    lowered = detect.with_overrides(cfg, flags(conf=0.10))

    assert lowered.model.conf == 0.10
    assert lowered.model.conf_debug == 0.10
    assert cfg.model.conf_debug == CONF_DEBUG  # the loaded config is untouched


def test_conf_flag_above_conf_debug_leaves_the_lower_threshold_alone(cfg):
    raised = detect.with_overrides(cfg, flags(conf=0.70))

    assert raised.model.conf == 0.70
    assert raised.model.conf_debug == CONF_DEBUG


# --- streams ---------------------------------------------------------------
#
# `run_stream` is driven by a stand-in source that yields five synthetic frames
# and says it is a stream. No camera is opened, no window is shown and no model
# is loaded; ByteTrack itself is real, because it is not a model.

FRAMES = 5
FRAME_W, FRAME_H = 80, 60
STREAM_NAME = "clip.mp4"  # not a file on disk: nothing here is a real video

APPEARED_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [log]
"""

CALL_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [{call: greet}]
"""

GREETING_HANDLERS = """
from core.events import on_detect


@on_detect(cls="person")
def greet(detection):
    print(f"greet saw {detection.cls_name}")
"""


class StubSource:
    """Five black frames, 0.1 s apart, from something that calls itself a stream."""

    is_stream = True
    is_camera = False
    fps = 10.0
    frame_size = (FRAME_W, FRAME_H)

    def __iter__(self):
        for index in range(FRAMES):
            yield Frame(
                image=np.zeros((FRAME_H, FRAME_W, 3), np.uint8),
                source=STREAM_NAME,
                index=index,
                time=index / self.fps,
            )

    def __len__(self) -> int:
        return FRAMES


@pytest.fixture(autouse=True)
def empty_event_bus():
    """The bus is module state; no test may leave a handler behind."""
    events.clear()
    yield
    events.clear()


@pytest.fixture
def stream_config(tmp_path, write_config):
    """Returns the path of a config whose rules file holds `rules_text`, output in `tmp_path`."""

    def build(rules_text: str) -> Path:
        rules = tmp_path / "rules.yaml"
        rules.write_text(rules_text, encoding="utf-8")
        return write_config(
            {
                "model.conf": CONF,
                "model.conf_debug": CONF_DEBUG,
                "classes": [],
                "output.save_json": True,
                "output.save_image": False,
                "output.dir": tmp_path.as_posix(),
                "rules.file": rules.as_posix(),
            }
        )

    return build


@pytest.fixture
def stream_cfg(stream_config):
    """Returns a loaded config whose rules file holds `rules_text`, output in `tmp_path`."""
    return lambda rules_text: load_config(stream_config(rules_text))


def stream_args() -> argparse.Namespace:
    return argparse.Namespace(source=STREAM_NAME, color=False, no_window=True)


def sure_and_near_miss() -> StubDetector:
    person = detection("person", 0.90)
    bottle = dataclasses.replace(detection("bottle", 0.30), bbox=(50.0, 30.0, 70.0, 50.0))
    return StubDetector([person, bottle])


def run(cfg) -> int:
    return detect.run_stream(
        StubSource(), sure_and_near_miss(), cfg, stream_args(), detect.Window(enabled=False, stream=True)
    )


def test_stream_writes_a_line_per_frame_and_prints_only_events(stream_cfg, tmp_path, capsys):
    heard = []
    events.on_detect()(heard.append)  # a catch-all: emit would reach it

    code = run(stream_cfg(APPEARED_RULES))

    assert code == 0
    lines = (tmp_path / "clip.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == FRAMES
    rows = [json.loads(line) for line in lines]
    assert [row["index"] for row in rows] == list(range(FRAMES))
    for row in rows:
        assert [(d["cls_name"], d["debug"]) for d in row["detections"]] == [
            ("person", False),
            ("bottle", True),
        ]
    printed = capsys.readouterr().out.splitlines()
    assert len([line for line in printed if "person_appeared" in line]) == 1
    assert not any("bottle" in line for line in printed)  # a near miss is never printed
    assert printed[-1].startswith(f"{FRAMES} frames, 1 events, wrote ")
    assert len(printed) == 2  # the event and the summary, nothing per frame
    assert heard == []  # on a stream the bus hears rules only, never emit


def test_a_call_action_runs_the_function_from_the_handlers_file(
    stream_cfg, tmp_path, capsys, monkeypatch
):
    handlers = tmp_path / "handlers.py"
    handlers.write_text(GREETING_HANDLERS, encoding="utf-8")
    monkeypatch.setattr(detect, "HANDLERS_PATH", handlers)

    code = run(stream_cfg(CALL_RULES))

    assert code == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed.count("greet saw person") == 1  # once: the rule fires once per track
    assert events.names() == set()  # the handlers are unhooked when the stream ends


def test_a_call_to_a_function_nobody_registered_stops_the_run(
    stream_cfg, tmp_path, capsys, monkeypatch
):
    handlers = tmp_path / "handlers.py"
    handlers.write_text("# no functions here\n", encoding="utf-8")
    monkeypatch.setattr(detect, "HANDLERS_PATH", handlers)

    code = run(stream_cfg(CALL_RULES))

    assert code == detect.EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.err.strip() == "unknown handler in rules.yaml: greet"
    assert not (tmp_path / "clip.jsonl").exists()  # stopped before the first frame


# --- the camera is released on every way out -------------------------------
#
# Driven through `main`, as a user runs it: `Source` and `Detector` are replaced
# by stand-ins, so no camera, window or model is ever opened. The spec names
# camera 9, an index nobody has plugged in, should a stand-in ever be bypassed.

CAMERA = "camera:9"

SAVE_FRAME_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: appeared
    class: person
    do: [save_frame]
"""

BROKEN_RULES = """
debounce:
  confirm_frames: 2
  cooldown: 100.0
rules:
  - name: person_appeared
    when: sometimes
    do: [log]
"""


class CameraStub:
    """A webcam stand-in: `frames` black frames, then `error` if one is given."""

    is_stream = True
    is_camera = True
    fps = 10.0
    frame_size = (FRAME_W, FRAME_H)

    def __init__(self, frames: int, error: BaseException | None = None) -> None:
        self._frames = frames
        self._error = error
        self.closes = 0

    def __iter__(self):
        for index in range(self._frames):
            yield Frame(
                image=np.zeros((FRAME_H, FRAME_W, 3), np.uint8),
                source=CAMERA,
                index=index,
                time=index / self.fps,
            )
        if self._error is not None:
            raise self._error

    def __len__(self) -> int:
        return 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False

    def close(self) -> None:
        self.closes += 1


def run_main(
    monkeypatch, config_path: Path, camera: CameraStub, weights: bool = True
) -> tuple[int, list[str]]:
    """Run `detect.py --source camera:9 --no-window`; return the code and every spec opened.

    `weights=True` stands in for weights on disk; False leaves the real check.
    """
    opened: list[str] = []

    def open_source(spec, cfg):
        opened.append(spec)
        return camera

    monkeypatch.setattr(detect, "CONFIG_PATH", config_path)
    monkeypatch.setattr(detect, "Source", open_source)
    monkeypatch.setattr(detect, "Detector", lambda cfg: sure_and_near_miss())
    if weights:
        monkeypatch.setattr(detect, "require_weights", lambda cfg: None)
    return detect.main(["--source", CAMERA, "--no-window"]), opened


def test_a_camera_that_stops_mid_stream_is_released_and_the_run_fails(
    stream_config, tmp_path, capsys, monkeypatch
):
    camera = CameraStub(frames=2, error=OSError("camera 9 stopped delivering frames"))

    code, _ = run_main(monkeypatch, stream_config(APPEARED_RULES), camera)

    assert code == detect.EXIT_STREAM_FAILED
    assert camera.closes > 0
    captured = capsys.readouterr()
    assert captured.err.strip() == "camera 9 stopped delivering frames"
    assert captured.out.splitlines()[-1].startswith("2 frames, ")
    [jsonl] = tmp_path.glob("*.jsonl")  # the writer was closed: both lines are there
    assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 2


def test_ctrl_c_releases_the_camera_and_ends_the_run_cleanly(
    stream_config, tmp_path, capsys, monkeypatch
):
    camera = CameraStub(frames=2, error=KeyboardInterrupt())

    code, _ = run_main(monkeypatch, stream_config(APPEARED_RULES), camera)

    assert code == 0
    assert camera.closes > 0
    assert capsys.readouterr().out.splitlines()[-1].startswith("2 frames, ")
    [jsonl] = tmp_path.glob("*.jsonl")
    assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 2


def test_a_file_that_cannot_be_written_is_a_usage_error_not_a_camera_failure(
    stream_config, capsys, monkeypatch
):
    def refuse(*args, **kwargs):
        raise OSError("could not encode image: out/events/camera_9_person_appeared_1.jpg")

    monkeypatch.setattr(output, "write_event_frame", refuse)
    camera = CameraStub(frames=FRAMES)

    code, _ = run_main(monkeypatch, stream_config(SAVE_FRAME_RULES), camera)

    assert code == detect.EXIT_USAGE
    assert camera.closes > 0
    captured = capsys.readouterr()
    assert captured.err.strip() == "could not encode image: out/events/camera_9_person_appeared_1.jpg"
    assert " frames, " in captured.out.splitlines()[-1]


def test_missing_weights_never_switch_the_camera_on(tmp_path, write_config, capsys, monkeypatch):
    rules = tmp_path / "rules.yaml"
    rules.write_text(APPEARED_RULES, encoding="utf-8")
    config_path = write_config(
        {"model.weights": (tmp_path / "absent.pt").as_posix(), "rules.file": rules.as_posix()}
    )

    code, opened = run_main(monkeypatch, config_path, CameraStub(frames=FRAMES), weights=False)

    assert code == detect.EXIT_USAGE
    assert opened == []
    assert capsys.readouterr().err.strip() == "run scripts/fetch_models.py first"


def test_a_broken_rules_file_never_switches_the_camera_on(stream_config, capsys, monkeypatch):
    camera = CameraStub(frames=FRAMES)

    code, opened = run_main(monkeypatch, stream_config(BROKEN_RULES), camera)

    assert code == detect.EXIT_USAGE
    assert opened == []
    assert "person_appeared" in capsys.readouterr().err


# --- colour: the flag or the config key ------------------------------------


@pytest.mark.parametrize(
    ("flag", "key", "coloured"),
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_colour_is_drawn_for_the_flag_or_the_config_key(
    flag, key, coloured, tmp_path, write_config, monkeypatch
):
    import core.attributes

    monkeypatch.setattr(core.attributes, "dominant_color", lambda image, bbox: "red")
    cfg = load_config(
        write_config(
            {
                "model.conf": CONF,
                "model.conf_debug": CONF_DEBUG,
                "display.color": key,
                "output.save_json": True,
                "output.save_image": False,
                "output.dir": tmp_path.as_posix(),
            }
        )
    )
    photo = Frame(image=np.zeros((60, 80, 3), np.uint8), source="photo.jpg", index=0)

    detect.run_images(
        [photo], StubDetector([detection("person", 0.90)]), cfg,
        argparse.Namespace(color=flag), detect.Window(enabled=False),
    )

    written = json.loads((tmp_path / "photo.json").read_text(encoding="utf-8"))
    assert written["detections"][0]["color"] == ("red" if coloured else None)


# --- a write failure is a usage error; any other OSError is not -------------


class FailingDetector:
    """A model that works for `good` frames, then raises the OSError it was given."""

    def __init__(self, good: int, error: OSError) -> None:
        self._good = good
        self._error = error
        self.calls = 0

    def __call__(self, frame: Frame) -> list[Detection]:
        self.calls += 1
        if self.calls > self._good:
            raise self._error
        return [detection("person", 0.90)]


def test_an_oserror_from_the_detector_mid_stream_propagates(stream_cfg, tmp_path, capsys):
    failing = FailingDetector(good=2, error=OSError("model file vanished"))

    with pytest.raises(OSError, match="model file vanished"):
        detect.run_stream(
            StubSource(), failing, stream_cfg(APPEARED_RULES), stream_args(),
            detect.Window(enabled=False, stream=True),
        )

    assert capsys.readouterr().err == ""  # not reported as an unwritable file
    assert len((tmp_path / "clip.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_a_stream_file_that_cannot_be_written_is_a_usage_error(
    stream_cfg, tmp_path, capsys, monkeypatch
):
    def refuse(self, *args, **kwargs):
        raise OSError("could not write out/clip.jsonl")

    monkeypatch.setattr(output.StreamWriter, "write", refuse)

    code = run(stream_cfg(APPEARED_RULES))

    assert code == detect.EXIT_USAGE
    assert capsys.readouterr().err.strip() == "could not write out/clip.jsonl"


def test_a_photo_whose_json_cannot_be_written_still_names_the_image_first(
    cfg, tmp_path, capsys, monkeypatch
):
    cfg = dataclasses.replace(cfg, output=dataclasses.replace(cfg.output, save_image=True))

    def refuse(*args, **kwargs):
        raise OSError("could not write photo.json")

    monkeypatch.setattr(output, "write_json", refuse)
    frame = Frame(image=np.zeros((60, 80, 3), np.uint8), source="photo.jpg", index=0)

    with pytest.raises(OSError, match="photo.json"):
        detect.process(frame, StubDetector([detection("person", 0.90)]), cfg, want_color=False)

    printed = capsys.readouterr().out.splitlines()
    assert printed[-1] == f"  wrote {tmp_path / 'photo_annotated.jpg'}"
