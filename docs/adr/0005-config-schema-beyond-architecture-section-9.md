# 0005. Config schema wider than ARCHITECTURE §9 (D04)

## Context

ARCHITECTURE §9 fixes the `config.yaml` schema, and the plan treated it as
complete. `bench.py` and `grab.py`, however, carry numbers of their own — camera
index, frame count, interval between frames, benchmark runs and warmup — which
the plan left as `argparse` defaults.

## Decision

The schema gains five keys beyond §9: `capture.camera`, `capture.count`,
`capture.interval`, `bench.runs`, `bench.warmup`. CLI flags still override them,
but the fallback value comes from `config.yaml`. ARCHITECTURE §9 is declared
stale and the addition is proposed to the user rather than made quietly.

## Why

Building the entry points showed that an `argparse` default is the same constant
in code that R56 forbids and ADR 0003 removed from the loader. Putting it in the
parser instead of the module changes nothing about the problem.

Considered and rejected:

- **Leaving them as `argparse` defaults.** Contradicts R56 and reintroduces
  exactly what 0003 just removed, in the files that are hardest to notice.
- **A separate config file for the tooling.** Splits the single source of
  numbers into two, which was the entire value R56 was buying.
- **Silently editing ARCHITECTURE.md to match.** The brief names it a source,
  not a working file; R60 asks for the divergence to be stated and the change
  proposed.

## Consequences

`config.yaml` and ARCHITECTURE §9 disagree until the user accepts the change,
and the document is the one that is wrong — anyone following it writes a config
that is short by five keys.

Combined with ADR 0003 that is worse than cosmetic: since a missing key is a
hard failure, a `config.yaml` copied from §9 will not start `detect.py` either,
even though the five keys have nothing to do with detection. The five keys are
mandatory for every entry point, not only for the two that use them.
