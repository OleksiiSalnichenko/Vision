# 0004. The aim stub returns a string (D03)

## Context

`core/aim.py` exists so that adding real pan-tilt servos later touches one file.
The spec's story assumed the stub would also make itself visible — the natural
reading was an arrow drawn on the annotated frame.

## Decision

`aim(dx, dy)` returns a direction arrow as a string. It does not receive the
frame and does not draw anything.

## Why

The contract in ARCHITECTURE §7 is `aim(dx, dy)` — there is no frame parameter,
so there is nothing to draw on. The stub exists to fix the attachment point for
phase 5, and that point is the signature.

Considered and rejected:

- **Widening the signature to take the frame.** It would change the single
  contract that the future servo code is supposed to plug into, so the stub
  would stop being a stub for the thing it stands in for. It also puts rendering
  inside a module whose job is actuation.
- **Drawing the arrow from `detect.py` instead.** Overlay decisions — colours,
  thicknesses, label layout — belong to `core/draw.py`. Adding a second place
  that paints on the frame costs more than the arrow is worth.

## Consequences

The stub is invisible in the OpenCV window. Nothing on screen shows that `aim`
ran, so it is confirmed only in the console or in tests — someone reviewing
phase 1 by eye will not see it and may assume it is missing.

When real servos arrive, the return value will most likely stop being a display
string and become a command or a pair of angles. Any caller that treats the
result as text to print will have to be revisited at that point; there should be
exactly one.
