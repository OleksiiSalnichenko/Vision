# 0016. Settings apply at once to the session; Save writes only changed values, line by line

## Context

At the 2026-09-27 briefing the user chose: settings take effect immediately on
the running session, and a button writes what changed to `config.yaml`, keeping
the file's comments.

## Decision

Settings are an always-open panel with no Apply button; every change goes to
the worker at once. The session holds its own `Config`, derived with
`dataclasses.replace`. "Save to config.yaml" compares it with the file and
writes only the differing values from a fixed set (`model.weights`,
`model.imgsz`, `model.conf`, `classes`, `display.center_line`,
`display.color`). The file is edited line by line — only the value after
`key:` is replaced, `classes` is rewritten as a block at its own indentation —
into a temporary file beside it, validated with `load_config`, then swapped in
with `os.replace`.

## Why

Considered and rejected:

- **A modal dialog with Apply / OK.** Contradicts the user's choice, and the
  threshold slider has to act immediately anyway; two interaction models in one
  window.
- **Saving every change automatically.** Experimenting in the window would
  silently change what `detect.py` does next time.
- **Loading and dumping the YAML with PyYAML.** Drops every comment, the
  commented-out alternatives and key order — in this project the comments in
  `config.yaml` are its documentation.
- **A round-trip YAML library (ruamel.yaml).** A new dependency to change six
  keys, and it still normalises formatting it does not own.
- **A separate UI overrides file.** A third override level; the project allows
  exactly two (CLI flag over `config.yaml`).
- **Writing the whole session config.** Would rewrite values the user never
  touched in the window.

## Consequences

The line editor understands only the shapes `config.yaml` actually uses
(scalars after `key:`, a block list for `classes`); a file hand-restructured
into other YAML forms is outside what it handles, and an invalid result is a
`ConfigError` naming the key with the file left untouched. Values changed but
not saved are lost with the window. Only the six listed keys can be saved from
the UI; everything else is still edited by hand.
