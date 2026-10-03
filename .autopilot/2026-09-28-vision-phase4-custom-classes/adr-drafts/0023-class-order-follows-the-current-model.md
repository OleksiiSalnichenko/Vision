# 0023. Class order of a trained model follows the current model's names

## Context

An 82-class model (ADR 0022) needs a fixed id for every class. COCO's own
annotation files number categories 1–90 with gaps; Ultralytics models number
the same 80 classes 0–79. `config.yaml classes`, `rules.yaml` and `handlers.py`
refer to classes by name, but the training labels, `data.yaml` and every exported
model store ids.

## Decision

Ids 0–79 are the current model's `names`, in the current model's order; ids
80 and up are `training.classes` in the order they are listed there (`pen` = 80,
`flower` = 81). COCO annotations are converted to these ids by category name,
never by COCO category id. A custom name that already exists among the base
names is refused.

## Why

Considered and rejected:

- **New classes first (0, 1), COCO after.** Every base class shifts by two; any
  tool, saved JSON or comparison keyed by id stops lining up with the stock
  model.
- **COCO category ids (1–90).** Leaves gaps and a mismatch with every model
  Ultralytics ships; the model would report ids that no other model in
  `models/` uses.
- **A fixed id table written into the training code.** A second copy of the
  class list that can drift from the model actually used as the base.
- **Allowing a custom name equal to a base name.** Two ids with one name; the
  whitelist and rules cannot tell them apart.

## Consequences

The base model and the trained one agree on ids 0–79, so swapping
`model.weights` between them keeps every rule, whitelist entry and handler
valid, and output files can be compared id for id.

Reordering or renaming a class in `training.classes` after a model is trained
changes the ids of the next model; the existing rules still work by name, but
labels made for the old order are not reusable without remapping.

The rough two-class model used for pre-labelling is the one exception: ids
0/1, no COCO. It is a labelling helper, never a `model.weights` value.
