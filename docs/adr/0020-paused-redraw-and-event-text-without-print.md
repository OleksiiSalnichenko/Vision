# 0020. Redraw on pause without counting a frame; event and summary text without printing (D01)

## Context

The plan assumed a stream session only ever advances with a new frame, and
that the Events panel could reuse the console line of a rule event. Task 03
came back BLOCKED on both: a paused video could not be redrawn after a click or
a slider move, and the event line existed only as a `print`.

## Decision

The stream session can redraw its last frame: re-split under the current
config, choose the target, draw the overlay — no detector, no rules, no file
writes — and a redraw does not count as a frame for releasing a locked target.
`core/output.py` builds the event line and the stream summary as strings;
`print_event` and `print_stream_summary` print exactly those strings.

## Why

Considered and rejected:

- **Feeding the last frame through a normal step again.** Runs the model,
  ages the tracker, can fire rules a second time and writes a duplicate JSONL
  line for a frame that was not new.
- **Letting a redraw count as a frame for the lock.** Found in repair 1: a few
  clicks or slider moves on pause would release the target the user had just
  locked, though no time passed in the video.
- **Capturing stdout in the worker to get the event line.** Swapping the global
  stdout from a background thread also swallows everything else printed or
  logged meanwhile, and races with the UI thread.
- **Formatting the line again in `ui/`.** A second copy of the console format
  that drifts from the one `detect.py` prints.

## Consequences

Task 03's zone widened to `core/pipeline.py`, `core/output.py` and, after the
repair, `core/target.py`: target choice now distinguishes a new frame from a
redraw, and every future caller has to say which it is. A paused frame shows
the new threshold's split at once, while ByteTrack's bands take effect only on
the next real frame.
