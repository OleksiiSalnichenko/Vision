"""The user's extension point: a callback per detection.

Phase 1 is deliberately the smallest thing that works -- a plain synchronous
call, once per detection, with no rules, no filtering beyond the class name and
no debouncing. Phase 2 layers rule evaluation and debouncing on top of this
same bus without changing either signature: a rule reaches a handler through
`call(name, detection)`, and `names()` lets the rules be checked at start-up.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from core.types import Detection

log = logging.getLogger(__name__)

Handler = Callable[[Detection], None]

# Class name -> handlers. `None` is the key for "every class". Module state,
# so it outlives any single run: `clear()` is what keeps one run's
# subscriptions out of the next one.
_handlers: dict[str | None, list[Handler]] = {}


def on_detect(cls: str | None = None) -> Callable[[Handler], Handler]:
    """Register the decorated function as a handler for `cls`.

    `cls=None` subscribes to every detection. The function is returned
    unchanged, so it stays callable on its own.
    """

    def register(handler: Handler) -> Handler:
        _handlers.setdefault(cls, []).append(handler)
        log.debug("handler %s registered for %s", handler.__name__, cls or "every class")
        return handler

    return register


def clear() -> None:
    """Drop every registration, leaving the bus as it was at import.

    The registry is module state and nothing removes a handler on its own, so
    anything that registers handlers and then hands control back -- a test, a
    second pass over another source -- resets the bus here. Without it the
    subscriptions of one run fire again during the next.
    """
    _handlers.clear()
    log.debug("handler registry cleared")


def emit(detection: Detection) -> None:
    """Call every handler subscribed to this detection's class, then the catch-alls.

    A handler that raises is logged and skipped: one broken user callback must
    not take down the detection loop or hide the detections behind it.
    """
    for handler in _subscribed(detection):
        _run(handler, detection)


def call(name: str, detection: Detection) -> None:
    """Call only the handlers named `name` that are subscribed to this class.

    This is how a rule's `call` action reaches user code: by function name,
    with the same class filter as `emit`, so a handler registered for
    `person` stays silent on a `cell phone` event. A raising handler is logged
    and skipped, as in `emit`.
    """
    for handler in _subscribed(detection):
        if handler.__name__ == name:
            _run(handler, detection)


def names() -> set[str]:
    """The function names of every registered handler, whatever its class."""
    return {handler.__name__ for handlers in _handlers.values() for handler in handlers}


def _subscribed(detection: Detection) -> list[Handler]:
    """Handlers for this detection's class first, then the catch-alls."""
    return _handlers.get(detection.cls_name, []) + _handlers.get(None, [])


def _run(handler: Handler, detection: Detection) -> None:
    try:
        handler(detection)
    except Exception:  # noqa: BLE001 -- user code, any failure is theirs
        log.exception("handler %s failed on a %s detection", handler.__name__, detection.cls_name)
