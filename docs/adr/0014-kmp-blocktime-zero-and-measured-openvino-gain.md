# 0014. `KMP_BLOCKTIME=0`, and OpenVINO measured at 1.54x rather than 2-3x (D03)

## Context

ARCHITECTURE §2 states OpenVINO is "roughly 2-3x faster than plain PyTorch on
this hardware", and §4 estimates about 25 FPS for the laptop on OpenVINO. The
plan took those figures as the expected outcome of the export and treated the
gain as a property of the runtime alone.

## Decision

The build proved otherwise. Without intervention OpenVINO ran at **0.57x** of
the `.pt` model — slower, not faster. Ultralytics imports torch whatever the
weights format, and torch's OpenMP threads spin-wait on all four cores after
each parallel region, starving OpenVINO's own threads.

`core/detector.py` sets `KMP_BLOCKTIME=0` before torch is imported, so idle
OpenMP threads yield immediately. With it, OpenVINO measured **1.54x** faster
than `.pt` (1.5–1.65x across runs), and the `.pt` path got faster too:
0.1025 → 0.079 s/frame. The measured numbers replace the estimates in the
README; updating ARCHITECTURE §2 and §4 is proposed to the user in the report.

## Why

The variable has to be set before the OpenMP runtime starts, so it belongs at
module top of the module that owns the import order — the same place and
discipline as the offline switches. It helps both backends, so there is no
format-specific branch.

Considered and rejected:

- **Accepting the result and keeping `.pt`.** Would discard the phase's main
  performance goal on the strength of a thread-scheduling artefact, not a
  property of OpenVINO.
- **Limiting torch threads (`torch.set_num_threads`).** Slows the `.pt` path,
  which is the default (ADR 0011), to make the opt-in path look good.
- **Asking the user to set the variable in their shell or in the README.** An
  environment step that is forgotten on the next machine, and the failure is
  silent — a slower run, not an error.
- **Making it a `config.yaml` key.** Nobody turns it; it is a correctness
  setting for the process, not a tunable number.
- **Reporting "2-3x" from the architecture.** The numbers are supposed to come
  from `bench.py`, and they disagree.

## Consequences

The performance budget is tighter than planned. At 1.5x the laptop does not
reach the ~25 FPS §4 assumed, and the Pi, which sets the real budget, should be
planned from measured factors rather than the §2 multiplier.

The phase-1 `.pt` numbers are superseded: anything comparing against them must
be re-measured with the variable set.

Like `YOLO_OFFLINE`, the setting only works if `core/detector.py` is imported
before anything imports torch. A new module that imports torch first silently
brings back the 0.57x regime — no error, only a slower benchmark.
