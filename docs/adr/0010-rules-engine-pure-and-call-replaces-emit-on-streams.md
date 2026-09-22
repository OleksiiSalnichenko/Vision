# 0010. Rules compute events, `detect.py` executes them, and `call` replaces per-frame `emit` on streams

## Context

Phase 1 has an event bus: handlers registered with `@on_detect(cls=...)`, and
`emit(detection)` called once per drawn detection. ARCHITECTURE §7 says phase 2
"layers rule evaluation and debouncing on top of this same bus without changing
its signature". Rules have actions — print a line, save a frame, call a user
function. `core/` has one module allowed to print and write (`core/output.py`),
and the debouncing requirement exists because a model flickering at 0.49/0.51
would otherwise fire hundreds of events.

## Decision

`core/rules.py` is a pure computation: `RuleEngine.update(time, detections)`
returns a list of `Event`s and does nothing else — no printing, no files, no
handler calls. `detect.py` executes each event's actions through `core/output.py`
and a new `events.call(name, detection)`, which invokes the handlers registered
under that function name and applies the same class filter as `emit`.

On a stream, `emit` is **not called at all**. `@on_detect` handlers are reached
only through a rule's `call` action. On photos, `emit` fires per drawn detection
exactly as in phase 1. `on_detect` and `emit` keep their signatures.

## Why

A pure engine can be driven in tests with synthetic detections and timestamps —
every condition, the cooldown and the 200-frame flicker case — without
capturing output or touching disk. It also keeps the "only `output.py` prints"
boundary intact.

Calling `emit` per frame on a stream reaches every handler 25 times a second
per object: precisely the undebounced flood the rules exist to stop. A handler
is where a user puts a side effect (a sound, a message, later a servo), so it
must only see debounced events.

Considered and rejected:

- **The engine executes its own actions.** Makes `core/rules.py` a second
  printing and writing module, and every rules test an I/O test.
- **Rules as subscribers on the bus** (the literal reading of §7: `emit` every
  detection, rules listen). Rules would be the only well-behaved listeners; any
  plain handler registered alongside them would still receive the raw per-frame
  stream.
- **Keeping per-frame `emit` and adding rules beside it.** Two routes to the
  same handlers, one debounced and one not; the user cannot tell which fired.
- **A new decorator for rule handlers.** Changes the bus surface the
  architecture promised to keep, for no capability `call` by name lacks.

## Consequences

The same handler behaves differently by source: on a photo it runs for every
drawn detection; on a video or camera it runs only if some rule names it. A
handler that no rule mentions is silently inert on streams. Mitigations are at
startup only: an unknown `call` name is an error naming it, and a rule whose
class can never match the handler's `cls` filter warns once.

`call` resolves by `__name__`, so two handlers with the same function name are
both invoked. `handlers.py` is imported only when some rule has a `call`.

`detect.py` now receives three control types besides `Detection` — `Event` and
`RuleSet` from the rules, `TargetState` from targeting. None carries new object
data (each wraps a `Detection`), but §7's "only type that crosses boundaries"
holds for consumers, not for the wiring; this is part of the proposal to the
user.
