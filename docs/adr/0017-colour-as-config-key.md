# 0017. Colour becomes a config key, `display.color`, alongside the `--color` flag

## Context

Since phase 1 the colour attribute has been switched on only by the `--color`
flag. Phase 3 puts colour in the settings panel, and Save must be able to
persist every setting in that panel.

## Decision

`config.yaml` gains `display.color: false`, added the project's way (config
file, dataclass, validation rule, test schema). `detect.py` computes colour
when the flag is given **or** the key is true; with the shipped `false` the
CLI behaves as before.

## Why

Considered and rejected:

- **A session-only toggle in the UI.** Save would silently skip one of the
  panel's settings; the user asked for "Save writes what changed".
- **Replacing the flag with the key.** Breaks existing command lines and the
  documented "every flag at once" invocation.
- **Shipping the key as `true`.** Changes `detect.py` output on a plain run and
  loads `sklearn` for users who never asked for colour.

## Consequences

One setting now has two switches. The flag can only turn colour on; with
`display.color: true` there is no CLI way to turn it off for one run. An
existing `config.yaml` without the key fails to load with a `ConfigError`
naming `display.color` — no defaults, by ADR 0003 — so a user's own copy must
gain the line.
