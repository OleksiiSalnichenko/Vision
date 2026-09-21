"""Where the pan-tilt servos will connect. For now: an arrow and nothing else.

The stub exists so that real hardware is one new file and zero edits anywhere
else. It deliberately holds no state, no calibration and no thresholds -- a
dead zone would be a tunable, and tunables live in `config.yaml`, not here.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# Arrow per (horizontal sign, vertical sign), with right and down positive --
# the same convention `core.geometry.offsets` uses.
_ARROWS = {
    (0, 0): "*",  # already on target
    (1, 0): "->",
    (-1, 0): "<-",
    (0, 1): "v",
    (0, -1): "^",
    (1, 1): "\\v",
    (-1, 1): "v/",
    (1, -1): "/^",
    (-1, -1): "^\\",
}


def aim(dx: int, dy: int) -> str:
    """Return the arrow pointing the way a camera would have to turn.

    `dx` and `dy` are the offsets from `core.geometry.offsets`: pixels, right
    and down positive. Nothing moves and nothing is driven -- this is the seam,
    not the mechanism.
    """
    arrow = _ARROWS[(_sign(dx), _sign(dy))]
    log.debug("aim %s (dx=%d, dy=%d)", arrow, dx, dy)
    return arrow


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)
