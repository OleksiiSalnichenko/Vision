"""core.events -- calling a registered handler by name, as a rule's `call` action does."""

import pytest

from core import events
from core.types import Detection


def detection(cls_name: str) -> Detection:
    # Built without `track_id` and `color`: both must stay optional, as in phase 1.
    return Detection(
        cls_id=0,
        cls_name=cls_name,
        conf=0.8,
        bbox=(10, 20, 30, 40),
        center=(20, 30),
        dx=-300,
        dy=-330,
        dx_pct=-0.9375,
        dy_pct=-0.9167,
    )


@pytest.fixture(autouse=True)
def empty_bus():
    events.clear()
    yield
    events.clear()


def test_call_runs_the_named_handler_and_no_other():
    seen = []

    @events.on_detect()
    def greet(det):
        seen.append(("greet", det.cls_name))

    @events.on_detect()
    def wave(det):
        seen.append(("wave", det.cls_name))

    events.call("greet", detection("person"))

    assert seen == [("greet", "person")]


def test_call_respects_the_class_filter_of_the_handler():
    seen = []

    @events.on_detect(cls="person")
    def greet(det):
        seen.append(det.cls_name)

    events.call("greet", detection("cell phone"))
    events.call("greet", detection("person"))

    assert seen == ["person"]


def test_call_with_an_unregistered_name_calls_nothing():
    seen = []

    @events.on_detect()
    def greet(det):
        seen.append(det.cls_name)

    events.call("on_phone", detection("person"))

    assert seen == []


def test_a_raising_handler_is_logged_and_the_next_one_still_runs(caplog):
    seen = []

    @events.on_detect(cls="person")
    def greet(det):
        raise RuntimeError("broken user code")

    @events.on_detect()
    def greet(det):  # noqa: F811 -- same name on purpose: both answer the call
        seen.append(det.cls_name)

    with caplog.at_level("ERROR"):
        events.call("greet", detection("person"))

    assert seen == ["person"]
    assert "greet" in caplog.text


def test_names_lists_every_registered_handler():
    @events.on_detect(cls="person")
    def greet(det):
        pass

    @events.on_detect()
    def on_phone(det):
        pass

    assert events.names() == {"greet", "on_phone"}


def test_names_is_empty_after_clear():
    @events.on_detect()
    def greet(det):
        pass

    events.clear()

    assert events.names() == set()


def test_emit_still_reaches_every_subscribed_handler_whatever_its_name():
    seen = []

    @events.on_detect(cls="person")
    def greet(det):
        seen.append("greet")

    @events.on_detect()
    def wave(det):
        seen.append("wave")

    @events.on_detect(cls="bottle")
    def pour(det):
        seen.append("pour")

    events.emit(detection("person"))

    assert seen == ["greet", "wave"]
