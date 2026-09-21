# 0006. `--conf` lowers `conf_debug` with it (D05)

## Context

Detection runs one inference pass with the floor set at `conf_debug` (0.25) and
splits the result: at or above `conf` (0.5) it is drawn, printed and emitted;
below it goes to JSON only, marked `debug: true`. The plan assumed `--conf` moved
the display threshold and nothing else.

## Decision

When `--conf` is given a value below `conf_debug`, `conf_debug` drops to the same
value, so the inference floor follows the flag.

## Why

The code showed the plan's version produces a flag that lies. With a fixed 0.25
floor, `--conf 0.1` changes no visible behaviour whatsoever: nothing below 0.25
was ever detected, so nothing new appears. A user lowering the threshold to hunt
for a missed object would conclude the object is undetectable, when in fact the
flag never reached the model.

Considered and rejected:

- **Keeping the floor and warning that `--conf` below 0.25 has no effect.**
  Honest, but the user still cannot get the thing they asked for, and the reason
  is an internal constant they did not set.
- **A second inference pass at the lower threshold.** Two runs cost twice for
  the same result — the reason the design uses one pass in the first place.
- **A separate `--conf-debug` flag.** Two knobs for one question, and the
  relationship between them still has to be defined somewhere. The near-miss
  band is a diagnostic, not a second control surface.

## Consequences

At `--conf` 0.25 or lower the near-miss band collapses: both thresholds are
equal, so no detection is marked `debug: true` and the JSON loses the near-miss
information — precisely when the user lowered the threshold because something
was being missed. The recovery is to read the low-confidence detections
themselves, which are now all in the visible set.

R16 and R32 continue to describe the default configuration, but they are no
longer invariants of every run. Anything reading the JSON must not assume a
debug band is present.
