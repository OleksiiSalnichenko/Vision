# 0015. The frame order moves into `core/pipeline.py`; `detect.py` becomes thin over it

## Context

The phase 3 desktop app needs exactly the per-frame order `detect.py` already
runs, for stills and streams. ARCHITECTURE.md §6 lists phase 3 as rewriting
nothing.

## Decision

The frame order (detect, track, `is_debug` split, colour, target, status,
overlay, rules, actions, writing) lives in one launch-agnostic module,
`core/pipeline.py`, used by both `detect.py` and `ui/`. `detect.py` keeps only
flags, console output and exit codes, and its behaviour does not change. The
pipeline never prints: a rule's `log` action goes to a callback the caller
supplies. This contradicts ARCHITECTURE.md §6 ("Rewritten: nothing" for phase
3); the deviation is recorded here and proposed to the user as an edit to §6,
not made silently.

## Why

Considered and rejected:

- **Copying the frame order into `ui/`.** Two pipelines that drift apart with
  the first edit, and a second caller of `is_debug` — the threshold split that
  the architecture keeps in exactly one place so near-misses are never drawn or
  printed by accident.
- **`ui/` calling `detect.run_stream` / `detect.process`.** They print to the
  console, own the OpenCV window and block until the stream ends; the GUI would
  depend on a CLI script and have to scrape stdout.
- **Honouring §6 literally.** Only possible through one of the two options
  above; the §6 line was written before any UI code existed (R32 says to
  propose a fix in that case).

## Consequences

"`detect.py` behaves byte-for-byte as before" is proven only by the existing
test suite; tests that patched a name which moved had to be pointed at its new
home with the same assertion. The single caller of `is_debug` is now
`core/pipeline.py`, so every note that says "`detect.py` is the only caller"
is stale. Calls to `output.*` and `events.*` inside the pipeline go through the
module attribute, because tests patch the module. ARCHITECTURE.md §6 stays
wrong until the user approves the proposed wording.

Expensive to reverse: undoing it means either re-inlining the order into
`detect.py` and duplicating it in `ui/`, or rewriting the UI worker.
