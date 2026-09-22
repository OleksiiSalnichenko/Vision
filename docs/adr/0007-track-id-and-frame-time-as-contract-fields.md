# 0007. `track_id` and `time` as fields of the data contract

## Context

Phase 2 adds two facts that every stream consumer needs: which object a
detection is across frames, and when in the stream a frame happened. The
overlay, the JSONL, target selection and the rules all read the first; the
`present for N seconds` rule and the cooldown read the second. ARCHITECTURE §7
fixes the field lists of `Detection` and `Frame`, says `Detection` is the only
type that crosses module boundaries, and the project convention says a
bookkeeping mark becomes a predicate (`is_debug`), never a new field.

## Decision

`Detection` gains `track_id: int | None = None` and `Frame` gains
`time: float = 0.0` (seconds from the start of the stream: container position
for a video file, a monotonic clock from the first frame for a camera, 0 for a
photo). Both have defaults, so every phase-1 constructor call still works and
photos leave them empty.

Both are changes to ARCHITECTURE §7. They are **proposed to the user in the
report, not yet accepted**; ARCHITECTURE.md is not edited.

## Why

`track_id` is not a mark derived from the detection's own fields, which is what
the predicate convention covers — `is_debug` can be recomputed from `conf` and
the config at any time. A track id is state produced by the tracker from the
history of earlier frames; no function of a single `Detection` can recover it.
It is data, and data that four consumers read belongs in the one type they all
already receive.

`time` cannot be derived from `index` either: `index / fps` is exact for a
file, but a camera drops frames under load, and then the frame count runs
behind the clock and every duration-based rule fires late.

Considered and rejected:

- **A predicate or lookup for `track_id`** (e.g. the tracker keeps an
  `id_of(detection)` map). The map lives in the tracker, so every consumer would
  need a handle on the tracker — the overlay and the JSON writer would start
  depending on the tracking module instead of on the contract.
- **A parallel structure** (`list[Detection]` plus `list[int]`, or a
  `TrackedDetection` wrapper). Two things to keep aligned through every filter
  and sort, or a second detection type for consumers — exactly what §7's "one
  type crosses boundaries" rule is there to prevent.
- **Wall-clock time read by the rules engine.** A video file processed faster
  or slower than real time would get durations that depend on the laptop's
  speed, and the rules could not be tested without sleeping.
- **`index / fps` everywhere.** Lies for the camera, as above.
- **Passing time as a separate argument next to the frame.** Every stage then
  carries two values that must never be separated; `Frame` already exists to be
  that pair.

## Consequences

The field list is the cross-module contract, and it is now wider than the
document that defines it. Until the user accepts the §7 proposal, ARCHITECTURE.md
describes types that no longer match the code. If the proposal is rejected,
reversing it is expensive: the overlay, the JSONL writer, target selection and
the rules engine all read `track_id`, and the rules' timing reads `Frame.time`.

`time == 0.0` does not mean "a photo" — it is also the first frame of every
stream. Code that needs to know whether it is on a stream asks the `Source`, not
the frame.

The predicate convention still stands; this ADR is the precedent for where its
line is: derivable from the detection itself → predicate; produced from other
frames → field.
