"""Your own code, run when a rule in `rules.yaml` says `{call: <name>}`.

This file is yours to edit. `detect.py` loads it on a video or webcam run
whenever some rule has a `call` action, and nothing in `core/` depends on what
is in it.

To add a function:

1. Write it here and register it with `@on_detect`. It receives one
   `core.types.Detection` -- the object that made the rule fire -- with
   `cls_name`, `conf`, `bbox`, `center`, `dx`/`dy`, `dx_pct`/`dy_pct` and
   `track_id`::

       @on_detect(cls="person")
       def greet(detection):
           print(f"hello, person #{detection.track_id}")

   `cls` limits the function to one class; leave it out to accept every class.

2. Call it by its function name from a rule in `rules.yaml`::

       - name: person_appeared
         when: appeared
         class: person
         do: [log, {call: greet}]

A rule naming a function this file does not register stops the run at start-up
with `unknown handler in rules.yaml: <name>`. A function that raises is logged
and skipped, so one bug here cannot stop the video.

Functions run on the detection loop itself: anything slow here (a network call,
a sleep) slows the video down by the same amount.
"""

from core.events import on_detect


@on_detect(cls="cell phone")
def on_phone(detection):
    """Called by the `phone_at_door` rule when a phone enters the `door` zone."""
    print(
        f"phone #{detection.track_id} at the door, "
        f"conf {detection.conf:.2f}, dx {detection.dx:+d} dy {detection.dy:+d}"
    )
