# 0024. Training settings live in their own strict file, not in config.yaml

## Context

Phase 4 brings about twenty tunable numbers: frame step, split fractions,
pseudo-label thresholds, COCO subset sizes, epochs, Kaggle slugs. The project
rule is that every user-turnable number lives in a config file with no defaults
in code (ADR 0003). The runtime never reads any of them, and the training
script runs on Kaggle, far from `config.yaml`.

## Decision

The training knobs live in `training/training.yaml`, loaded by its own loader
under the same rules as `config.yaml`: every key required, a missing key is an
error naming it, an unknown key is a warning. A copy of the file travels inside
every dataset build, and the Kaggle script reads that copy. `core/config.py` and
`config.yaml` are not extended.

## Why

Considered and rejected:

- **Adding a `training:` section to `config.yaml`.** Every runtime start would
  validate keys it never uses, a broken training value would stop the detector,
  and the app's Save, which rewrites `config.yaml` line by line, would have
  twenty more lines to step around.
- **Command-line flags with defaults in code.** Breaks the no-defaults rule and
  leaves no record of what a given model was trained with.
- **Reading settings on Kaggle from the notebook source.** A second place to edit
  values, and the build would not say which settings it was made for.

## Consequences

Two config files with two loaders that must apply the same rules; a change to
the strictness of one is not automatically a change to the other.

A model's training settings are reproducible from its build folder, since the
copy travels with the data.

The Kaggle username is a placeholder in this file until the user fills it in;
network commands refuse with one sentence until then.
