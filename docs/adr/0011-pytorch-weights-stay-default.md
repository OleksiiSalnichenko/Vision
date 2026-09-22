# 0011. `.pt` weights stay the default; OpenVINO is one config line away

## Context

Phase 2 exports YOLO26n to OpenVINO and the detector accepts either the `.pt`
file or the exported folder; which one runs is `model.weights` in
`config.yaml`. OpenVINO is measurably faster on this laptop (ADR 0014). The
exported folder exists only after `scripts/export_openvino.py` has run, which in
turn needs the `.pt` from `scripts/fetch_models.py`.

## Decision

`config.yaml` ships with `model.weights: models/yolo26n.pt`. Switching to
OpenVINO is editing that one line to `models/yolo26n_openvino_model`; the README
shows the line next to the measured numbers.

## Why

A fresh clone has to work after the one networked step and nothing else. With
OpenVINO as the default, the first `detect.py` run after `fetch_models.py` would
fail with "run scripts/export_openvino.py first" — a correct message, but a
second mandatory setup step introduced for a speed-up the user has not asked
for yet.

Considered and rejected:

- **OpenVINO as the default.** Adds a second mandatory step to setup, as above.
- **Exporting inside `fetch_models.py`.** Mixes the one networked script with an
  offline, slow, `openvino`-dependent conversion; a failed export would look
  like a failed download.
- **Auto-exporting on first run from the detector.** A hidden, slow side effect
  in the inference path, and `core/` writing into `models/`.
- **Preferring the OpenVINO folder automatically when it exists.** The same
  config would run different backends on different machines — an abstraction
  around model choice that the architecture explicitly forbids, and the reason
  results change would not be visible in `config.yaml`.

## Consequences

Out of the box the laptop runs about 1.5x slower than it could; getting the
speed-up is a deliberate user action. Changing `model.imgsz` requires re-running
the export, because the OpenVINO model has a static input shape — with the
`.pt` default that trap only exists for users who opted in.

Cheap to reverse: flipping the default later is one line plus a README edit,
provided setup instructions gain the export step at the same time.
