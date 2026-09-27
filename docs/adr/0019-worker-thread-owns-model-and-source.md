# 0019. One worker thread owns the model, the source and the session; the UI shows only the newest frame

## Context

A frame costs 0.05–0.08 s of inference on this laptop and a model load takes
seconds; the window must never freeze, and a camera must be released on every
exit path, including closing the window.

## Decision

A single `QThread` worker owns the detector, the source and the stream
session. The UI thread never touches them: it sends commands through queued
signals and receives per-frame results carrying a copy of the canvas. If the
UI falls behind, the newest frame is shown and older ones are dropped; every
frame is still written to `out\` by the worker. The model is loaded once and
lives across sources. Closing the window stops the worker and waits for the
thread to finish before the window goes.

## Why

Considered and rejected:

- **Inference on the UI thread driven by a timer.** Freezes the window for
  every frame and for the whole model load.
- **A separate process.** Frames pickled across a boundary, a camera handle
  living in another process to be released, and one more model in memory; the
  Windows spawn start-up re-imports everything.
- **A new thread per opened source.** Reloads the model on every open.
- **Queueing every frame for display.** When painting is slower than inference
  the view lags further behind the camera the longer it runs.
- **Sharing the detector between threads behind locks.** More race surface for
  no gain; one owner makes release on every path a single `finally`.

## Consequences

Closing the window during a model load waits until the load ends. Stop is
checked between frames only. The displayed rate can be lower than the
processed rate, and the files, not the screen, are the complete record. Each
shown frame costs one array copy. `handlers.py` functions now run on the worker
thread, so a handler that touches Qt widgets would break. UI tests need
`pytest-qt` and the offscreen platform.
