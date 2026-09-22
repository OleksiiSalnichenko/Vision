# 0008. ByteTrack thresholds derived from `model.conf` and `conf_debug`

## Context

ByteTrack associates detections in two bands: a high-confidence band that can
start and extend tracks, and a low-confidence band that only extends tracks it
already has. It is configured by three thresholds (`track_high_thresh`,
`new_track_thresh`, `track_low_thresh`). The project already has two
confidence thresholds with exactly these meanings: `model.conf` (drawn and
acted on) and `model.conf_debug` (the inference floor; the near-miss band
between them). Every tunable number is supposed to live in `config.yaml`.

## Decision

The three thresholds are not configuration keys. The tracker computes them:
`track_high_thresh = new_track_thresh = model.conf`,
`track_low_thresh = model.conf_debug`. `config.yaml` carries only the tracker's
own knobs: `tracker.track_buffer`, `tracker.match_thresh`, `tracker.fuse_score`.

## Why

The two bands of ByteTrack and the two bands of this project are the same
question asked twice. Deriving one from the other makes the near-miss band
useful for a second purpose — a person dipping to 0.4 for a few frames keeps
their id instead of getting a new one — without ever drawing the near-miss.
It also means `--conf` on a stream moves the tracker with it, with no extra
flag.

Considered and rejected:

- **Three `tracker.*` threshold keys of their own.** They would duplicate
  numbers that already exist, and nothing keeps them consistent. With
  `new_track_thresh` below `conf`, the tracker starts tracks on objects that are
  never drawn, so ids appear to skip; with `track_low_thresh` above
  `conf_debug`, the near-miss band the model already paid for never reaches the
  tracker. And `--conf` would change what is drawn but not what is tracked.
- **Ultralytics' stock `bytetrack.yaml` values.** Its low threshold sits below
  our inference floor, so part of its low band can never be populated — the
  numbers describe a detector that is not this one.
- **Deriving with offsets or ratios** (e.g. high = `conf` − 0.1). A hidden
  constant in code, which the config convention forbids, for no demonstrated
  gain.

## Consequences

Tracker sensitivity cannot be tuned independently of display sensitivity. If a
real clip ever shows that tracks should start below the drawing threshold, this
ADR is what has to be reopened, and the fix is new config keys plus rules in
`core/config.py`.

Combined with ADR 0006: `--conf` at or below `conf_debug` pulls the floor down
with it, the near-miss band collapses, and ByteTrack's low band is empty. On
those runs, tracks survive a dip in confidence worse than at the defaults — the
user lowering the threshold gets more detections but less stable ids.
