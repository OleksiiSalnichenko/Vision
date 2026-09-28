# 0021. OpenVINO becomes the default model format

Supersedes 0011.

## Context

ADR 0011 kept `models/yolo26n.pt` as the shipped `model.weights` so a fresh
clone would run after `scripts/fetch_models.py` alone; OpenVINO was one config
line away for whoever wanted the speed-up. ADR 0014 measured that speed-up on
this laptop at 1.54x (`bus.jpg`, 3 warm-up + 10 runs: `.pt` 0.079 s/frame,
OpenVINO 0.051 s/frame).

During phases 2 and 3 the user ran both formats on the live webcam, compared the
FPS, and chose the faster one: the goal is the fastest detection this CPU can
give, and OpenVINO is it. ADR 0011 rejected the OpenVINO default because it was
"a speed-up the user has not asked for yet" — the user has now asked for it.

## Decision

`config.yaml` ships with `model.weights: models/yolo26n_openvino_model`, the
`.pt` line kept commented out above it as the PyTorch alternative. Setup gains
one mandatory offline step after the networked one:

```
venv\Scripts\python scripts\fetch_models.py
venv\Scripts\python scripts\export_openvino.py
```

The README setup, its OpenVINO section and its troubleshooting say so.

## Why

The trade-off ADR 0011 weighed — a second setup step against a 1.5x faster
run — is settled by the user's own measurement and choice. The second step is
cheap: offline, idempotent (`skip:` when the folder exists), and when it is
forgotten the detector already stops with one sentence, "run
scripts/export_openvino.py first", and exit code 2, before any camera opens.

Considered and rejected (the same alternatives ADR 0011 rejected, for the same
reasons, still hold):

- **Keeping `.pt` as the default.** Runs the laptop about 1.5x slower than it
  can, against the user's explicit choice.
- **Exporting inside `fetch_models.py`.** Mixes the one networked script with an
  offline, slow, `openvino`-dependent conversion; a failed export would look
  like a failed download.
- **Auto-exporting on first run from the detector.** A hidden, slow side effect
  in the inference path, and `core/` writing into `models/`.
- **Preferring the OpenVINO folder automatically when it exists, else `.pt`.**
  The same config would run different backends on different machines, and the
  reason would not be visible in `config.yaml` — the abstraction around model
  choice the architecture forbids.

## Consequences

A fresh clone needs `scripts/export_openvino.py` after `scripts/fetch_models.py`
before the first `detect.py`, `bench.py` or `app.py` run; skipping it is the
"run scripts/export_openvino.py first" error, not a silent fallback.

The OpenVINO model has a static input shape, so changing `model.imgsz` now
affects every user: it needs `scripts\export_openvino.py --force`, otherwise the
folder still carries the old size. The desktop app greys out `imgsz` for an
OpenVINO model for the same reason.

The `openvino==2026.3.1` pin (ADR 0013) and `KMP_BLOCKTIME=0` (ADR 0014) are now
on the default path rather than the opt-in one: an `openvino` upgrade or a
module importing torch before `core/detector.py` degrades the out-of-the-box
run, not only the opt-in one.

Cheap to reverse: going back to PyTorch is one line of `config.yaml`,
`model.weights: models/yolo26n.pt`, and needs no export.
