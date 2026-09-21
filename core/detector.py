"""Inference and the filters around it.

The module owns three things and hides all of them: loading the weights from an
explicit local path, running one pass over a frame, and turning raw boxes into
`Detection` objects. No NMS is added here -- YOLO26 is NMS-free and removes its
own duplicates; porting NMS from YOLO11 examples would only cost accuracy.

Nothing in this module reaches the network. `ultralytics` is imported lazily,
after the weights file has been confirmed on disk, so that the missing-weights
path costs neither a model load nor a download attempt.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import Config
from core.geometry import offsets
from core.types import Detection, Frame

log = logging.getLogger(__name__)

# Quoted verbatim from ARCHITECTURE.md section 7 and the brief. Users grep for
# this sentence, so it is the whole message and nothing is appended to it.
MISSING_WEIGHTS_MESSAGE = "run scripts/fetch_models.py first"


class Detector:
    """Runs one model over frames and returns detections in source pixels."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        weights = Path(cfg.model.weights)

        # Before anything else: Ultralytics downloads weights from GitHub when
        # it is handed a name it cannot find on disk. On a machine with no
        # network that turns into a confusing crash somewhere deeper, so the
        # check happens here, before `ultralytics` is even imported.
        if not weights.is_file():
            log.error("weights file not found: %s", weights.resolve())
            raise FileNotFoundError(MISSING_WEIGHTS_MESSAGE)

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
