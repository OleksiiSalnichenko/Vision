# 0018. Threshold and classes change on a running stream without reloading or resetting

## Context

The slider and the class checkboxes must act from the next frame on video and
camera. ByteTrack's high and new-track bands are derived from `model.conf`
(ADR 0008) and fixed when the tracker is built; the class whitelist was fixed
when the detector was built.

## Decision

The tracker's bands can be changed in place without dropping tracks, and the
detector's class filter can be replaced between frames without reloading the
model. A model reload happens only for a different weights path or `imgsz`, in
the worker between frames, keeping the tracker, target lock and rule state. A
failed reload keeps the previous model.

## Why

Considered and rejected:

- **Changing only the drawn / near-miss split.** An object at 0.4 with the
  slider at 0.3 would be drawn but never get a track id, so it could never be
  a target or fire a rule.
- **Building a new tracker on each change.** ByteTrack's id counter is
  process-wide, so numbering restarts, the lock is lost and rule cooldowns,
  keyed by track id, fire again for objects already seen.
- **Reloading the model for a class change.** Seconds of stall (the OpenVINO
  folder compiles twice) for what is a per-frame filter.
- **Resetting the stream on any settings change.** Turns every slider drag into
  a restart of tracking and rules.

## Consequences

The tracker now edits ByteTrack's arguments after construction, which depends
on how Ultralytics stores them; an Ultralytics upgrade can break this quietly,
and it is hidden inside `core/tracker.py`. Tracks started under the old
threshold keep living under the new one. An unknown class name is refused with
the same message as at start-up and the previous filter stays. `imgsz` cannot
change for an OpenVINO model at all — the export is static.
