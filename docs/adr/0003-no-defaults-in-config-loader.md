# 0003. No defaults in the config loader (D02)

## Context

The spec first described `core/config.py` as owning "the default schema": a set
of built-in values that `config.yaml` would override, so a short or older config
file would still start.

## Decision

`core/config.py` carries no default values at all. A missing key raises
`ConfigError` naming the key, exactly as a wrong type or an out-of-range value
does; an unknown key is a warning. A new setting is added to `config.yaml`, not
to the module.

## Why

Writing the loader made the contradiction concrete: a default inside a module is
the same tunable number as a constant in code, only in a less obvious place.
R56 says every tunable number lives in `config.yaml`, and a default schema means
the effective value of a setting depends on two files at once — the one the user
edits and the one they do not.

Considered and rejected:

- **Built-in defaults with file overrides.** Fails R56, and makes silent drift
  possible: the app runs with a number nobody wrote down.
- **A shipped `default.yaml` merged over the user's file.** Moves the same
  problem one level up and adds merge semantics to reason about — which file
  won, and why, becomes a question the user has to ask.

## Consequences

Every new key is a breaking change for existing config files: the app refuses to
start until the key is present. That is deliberate but unpleasant, and it will
bite on the first upgrade after a key is added.

There is no "just run it" path with a partial config — copying a truncated
example fails immediately. The compensation is that failure is loud and names
the key, so the fix is one line, and the config file can be trusted as the
complete account of the program's numbers.
