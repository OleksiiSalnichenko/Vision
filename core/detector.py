"""Inference and the filters around it.

The module owns three things and hides all of them: loading the weights from an
explicit local path, running one pass over a frame, and turning raw boxes into
`Detection` objects. No NMS is added here -- YOLO26 is NMS-free and removes its
own duplicates; porting NMS from YOLO11 examples would only cost accuracy.

Nothing in this module reaches the network. `ultralytics` is imported lazily,
after the weights file has been confirmed on disk, so that the missing-weights
path costs neither a model load nor a download attempt -- and Ultralytics' own
outbound traffic is switched off at the top of this file, before that import
can happen.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from core.config import Config
from core.geometry import offsets
from core.types import Detection, Frame

# Ultralytics decides once, while `ultralytics.utils` is being imported,
# whether it may go out: `ONLINE = is_online()` resolves a DNS name and freezes
# the answer, and the analytics thread, the Sentry hook and the pip update
# check all read that frozen flag afterwards. `YOLO_OFFLINE` is the switch
# version 8.4 reads, and it is only read during that import -- set a line too
# late it changes nothing, while the analytics POST to google-analytics.com
# still leaves on every `predict`, swallowed, from a background thread.
#
# This module is where it belongs: it is the only one in the project that
# imports `ultralytics`, and `detect.py`, `bench.py` and the tests all reach a
# model through it, so no entry point can get in ahead of this line.
# `scripts/fetch_models.py` deliberately stays outside this import path -- the
# one-time weight download is the one step that is meant to go online.
#
# It is set here and not in the user's Ultralytics `settings.json` because that
# file belongs to the machine, not to this repository: a clone on a bare Pi has
# to be offline the moment it is checked out, with nothing configured by hand.
os.environ["YOLO_OFFLINE"] = "1"
# The other runtime network path: Ultralytics will pip-install a dependency it
# finds missing. Installing is `requirements.txt`'s job and happens before a
# run, never during one.
os.environ["YOLO_AUTOINSTALL"] = "0"

# Not a network switch but a speed one, and it has the same timing constraint.
# torch on Windows ships Intel OpenMP, whose worker threads busy-wait 200 ms
# after every parallel region before they sleep. Ultralytics runs its pre- and
# post-processing in torch, so those threads are still spinning on every core
# while the next frame's inference starts -- and an OpenVINO model, which runs
# on threads of its own, loses the cores to them: measured on this 4-core
# laptop, 0.18 s per frame instead of 0.05, slower than the `.pt` it replaces.
# With no spin the `.pt` path gets faster too. OpenMP reads the variable once,
# when its runtime starts, so it has to be set before torch is imported --
# which is why it sits here, above the only imports that bring torch in.
os.environ["KMP_BLOCKTIME"] = "0"

# OpenVINO has telemetry of its own, in the separate `openvino_telemetry`
# package that `pip install openvino` brings along. `import openvino` imports
# `openvino.tools.ovc` to expose `convert_model`, and that module, at import
# time, starts a Google Analytics client and posts a "general_import" event;
# `convert_model` posts several more during an export. The client runs
# opt-out: with no consent file in the user profile it counts as consent, and
# the POST leaves from a background thread with its failure swallowed -- on
# every model load, not only on the first.
#
# The package has no switch of its own beyond "is this a CI job", which would
# mean lying about the environment to every other library in the process.
# OpenVINO itself, though, imports it inside `try/except ImportError` and falls
# back to `openvino.tools.ovc.telemetry_stub`, whose methods do nothing. A
# `None` in `sys.modules` makes that import fail for this process only, so the
# stub is what gets used. Like `YOLO_OFFLINE`, it has to be in place before the
# first `import openvino`, and like it, it stays out of the user profile: the
# consent file there belongs to the machine, not to this repository.
#
# Assigned, not `setdefault`: if something imported the package ahead of this
# module, `setdefault` would keep the real one and leave telemetry on without a
# word. The assignment still blocks every later import of it, and the warning
# says that whatever imported it first may already have sent its event.
log = logging.getLogger(__name__)
if sys.modules.get("openvino_telemetry") is not None:
    log.warning(
        "openvino_telemetry was imported before core.detector; "
        "switching it off now may be too late for that import"
    )
sys.modules["openvino_telemetry"] = None

# Quoted verbatim from ARCHITECTURE.md section 7 and the brief. Users grep for
# this sentence, so it is the whole message and nothing is appended to it.
MISSING_WEIGHTS_MESSAGE = "run scripts/fetch_models.py first"

# The OpenVINO counterpart: a `*_openvino_model` folder only exists after the
# offline export, never after `fetch_models.py`, so that is the step to name.
MISSING_EXPORT_MESSAGE = "run scripts/export_openvino.py first"

# How Ultralytics names an exported OpenVINO model: `<stem>_openvino_model/`
# next to the `.pt`, with the network in an `.xml` file inside.
OPENVINO_SUFFIX = "_openvino_model"


class Detector:
    """Runs one model over frames and returns detections in source pixels."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        weights = Path(cfg.model.weights)

        # Before anything else: Ultralytics downloads weights from GitHub when
        # it is handed a name it cannot find on disk. On a machine with no
        # network that turns into a confusing crash somewhere deeper, so the
        # check happens here, before `ultralytics` is even imported.
        require_weights(cfg)

        # `YOLO` picks the backend from the path itself -- a `.pt` file or an
        # OpenVINO folder -- so nothing below this line knows the format.
        from ultralytics import YOLO  # noqa: PLC0415 -- deliberately lazy

        self._model = YOLO(str(weights))
        self._class_ids = _whitelist_ids(self._model.names, cfg.classes)

    def __call__(self, frame: Frame) -> list[Detection]:
        """Return every detection at or above `conf_debug`, best first.

        One pass, two thresholds: the model runs at `conf_debug` and the list
        keeps the near-misses as well. Running it twice would cost twice and
        return the same boxes. `is_debug` tells the two groups apart.
        """
        height, width = frame.image.shape[:2]

        results = self._model.predict(
            frame.image,
            imgsz=self._cfg.model.imgsz,
            conf=self._cfg.model.conf_debug,
            classes=self._class_ids,
            verbose=False,
        )

        detections = [
            _detection(box, self._model.names, (width, height))
            for result in results
            for box in result.boxes
        ]
        detections.sort(key=lambda det: det.conf, reverse=True)
        return detections


def require_weights(cfg: Config) -> None:
    """Raise `FileNotFoundError` unless `model.weights` is a model Ultralytics can load.

    The check `Detector` makes first, public so a caller can make it before
    anything costly -- switching a webcam on -- without loading the model.
    A file is taken as it is. A folder has to hold an OpenVINO `.xml`: an
    export interrupted half-way leaves the folder behind, and handing that to
    Ultralytics ends in a traceback about a missing file deep inside it.
    """
    weights = Path(cfg.model.weights)
    if weights.is_file():
        return
    if weights.is_dir() and any(weights.glob("*.xml")):
        return

    log.error("weights not found: %s", weights.resolve())
    if weights.name.endswith(OPENVINO_SUFFIX):
        raise FileNotFoundError(MISSING_EXPORT_MESSAGE)
    raise FileNotFoundError(MISSING_WEIGHTS_MESSAGE)


def is_debug(detection: Detection, cfg: Config) -> bool:
    """True for a near-miss: at or above `conf_debug`, but below `conf`.

    `Detection` carries no flag of its own -- its fields are a fixed contract
    (ARCHITECTURE.md section 7) -- so the mark is this predicate, and the
    threshold it compares against stays in `config.yaml`.
    """
    return detection.conf < cfg.model.conf


def _detection(box, names: dict[int, str], frame_size: tuple[int, int]) -> Detection:
    """Build one `Detection` from an Ultralytics box.

    Coordinates arrive already mapped back into source-image pixels: the
    letterbox transform is Ultralytics' own and it undoes it before returning.
    """
    cls_id = int(box.cls.item())
    x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
    center, dx, dy, dx_pct, dy_pct = offsets((x1, y1, x2, y2), frame_size)

    return Detection(
        cls_id=cls_id,
        cls_name=names[cls_id],
        conf=float(box.conf.item()),
        bbox=(x1, y1, x2, y2),
        center=center,
        dx=dx,
        dy=dy,
        dx_pct=dx_pct,
        dy_pct=dy_pct,
    )


def _whitelist_ids(names: dict[int, str], classes: list[str]) -> list[int] | None:
    """Translate configured class names into model class ids.

    An empty whitelist means every class the model knows, which Ultralytics
    expresses as `classes=None`. A name the model does not know is a typo in
    `config.yaml` and is reported as one instead of quietly matching nothing.
    """
    if not classes:
        return None

    by_name = {name: cls_id for cls_id, name in names.items()}
    unknown = [name for name in classes if name not in by_name]
    if unknown:
        known = ", ".join(sorted(by_name))
        raise ValueError(f"unknown class names in config: {unknown} -- model knows: {known}")

    return [by_name[name] for name in classes]
