# 0001. Frame offset geometry

## Context

Every consumer downstream of detection — console lines, JSON, the `aim(dx, dy)`
stub, and later servo aiming and phase-2 rules — reads the same two numbers.
Inference itself runs letterboxed at `imgsz: 640`, while the user's photos are
any size.

## Decision

Offsets are computed in the pixels of the source image: `dx = cx - width/2`,
`dy = cy - height/2`, with right and down positive. The normalised pair is
`dx_pct = dx / (width/2)`, `dy_pct = dy / (height/2)`, so the range is -1..1 and
the frame edge is exactly 1. Letterbox padding is not undone by us; Ultralytics
returns box coordinates already in source pixels.

## Why

The number has to describe the user's photo, not the padded model input, because
that is what the user checks by eye and what a pan-tilt loop will eventually act
on. Half-frame normalisation makes "edge of frame" equal to 1, which is the unit
an aiming loop wants.

Considered and rejected:

- **Computing in 640x640 model coordinates.** Would mean reversing the letterbox
  ourselves, which Ultralytics has already done — extra work and a second place
  for the same bug to live.
- **Dividing by full width/height.** Range becomes -0.5..0.5, the frame edge is
  0.5, and every consumer carries a factor of two it did not ask for.
- **Maths convention (up positive).** Inverts against image coordinates, so
  every drawing call would flip the sign back. One convention, held everywhere,
  is cheaper than two.

## Consequences

The sign and scale convention is now baked into the JSON files, the console
format and the `aim` contract at once. Changing it later means touching every
consumer and invalidating every JSON already written — this is the most
expensive line in the project to move.

On non-square frames the two axes are not comparable in pixels: `dx_pct = 0.5`
on a wide photo is more pixels than `dy_pct = 0.5`. Any future servo mapping has
to fold the aspect ratio back in; the offsets themselves will not do it.
