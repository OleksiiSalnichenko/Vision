# 0009. Ultralytics' `BYTETracker` called directly; the offline import order covers `core/tracker.py`

## Context

ARCHITECTURE §10 asks for ByteTrack. The Pi, not the laptop, sets the
performance budget, which favours an existing optimised implementation. Phase 1
established an invariant: `core/detector.py` is the only module that imports
`ultralytics`, because it sets `YOLO_OFFLINE` and `YOLO_AUTOINSTALL=0` at module
top before that import, and Ultralytics reads the offline switch exactly once,
on first import. The detector must stay a detector: one inference pass, the
drawn / near-miss split in `detect.py`, class filtering from `config.yaml`.

## Decision

`core/tracker.py` wraps `ultralytics.trackers.byte_tracker.BYTETracker`
directly: the tracker receives the already-filtered detections packed into an
Ultralytics `Boxes` and maps the returned rows back to the input detections by
their index. `model.track()` is not used.

The offline invariant is widened to two modules in a fixed order:
`ultralytics` is imported only by `core/detector.py` and `core/tracker.py`, and
the tracker imports `core.detector` as its first import and `ultralytics` lazily,
after it. `scripts/export_openvino.py` does the same. `tests/test_offline.py`
gains a subprocess case that imports `core.tracker` in a clean process.

## Why

Calling the tracker directly keeps tracking a separate stage fed by the same
list the rest of the pipeline sees, so the detector, the class whitelist and
the `is_debug` split are untouched, and the tracker can be tested on synthetic
moving boxes without a model.

Considered and rejected:

- **`model.track()`.** Fuses inference and tracking into one call, so the
  detector would own tracking state, and tracking would happen before our class
  filter and threshold split rather than after. Its thresholds come from an
  Ultralytics YAML file — a second source of numbers beside `config.yaml` — and
  testing tracking would require loading a model.
- **Our own ByteTrack.** Kalman filter plus assignment, all of it ours to get
  right and test, for an algorithm that already exists optimised; the Pi budget
  argues against it.
- **A different tracking library.** A new dependency whose network behaviour
  would have to be audited from scratch, when the one already installed is
  covered by the offline switches.
- **Keeping one importing module by routing the tracker through
  `core/detector.py`.** Puts identity-across-frames into the inference module,
  mixing two responsibilities to preserve a rule whose actual purpose is import
  order, not module count.

## Consequences

`BYTETracker` and `Boxes` are Ultralytics internals, not a public API. An
Ultralytics upgrade can break `core/tracker.py` without breaking the detector;
the tracker tests are the alarm.

ByteTrack needs `lap`; without it Ultralytics would try to auto-install it, and
auto-install is switched off. `lap` is therefore a hard entry in
`requirements.txt`, and a missing `lap` is a failure, not a download.

The invariant is now an ordering rule, which is easier to break than a
one-module rule: any new module that imports `ultralytics` (or `core.tracker`
before `core.detector` is loaded by someone else) silently re-enables telemetry.
The subprocess test catches only the entry points it imports. CLAUDE.md's rule
has to be updated to the two-module wording.
