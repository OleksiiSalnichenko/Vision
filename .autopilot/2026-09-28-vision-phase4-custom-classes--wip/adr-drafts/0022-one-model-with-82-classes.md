# 0022. One model with 82 classes: COCO kept in training, user frames pseudo-labelled

## Context

`pen` and `flower` are not among the 80 COCO classes, so the stock model never
reports them. A model fine-tuned only on the new classes sees only those
classes: it would stop reporting `person`, `cell phone` and the rest, which the
existing rules (`phone_at_door`), the class whitelist and `handlers.py` depend on.
The user asked for the trained objects to be added to the list, next to the
80 standard ones, and accepted one model for all 82 when offered.

## Decision

Phase 4 trains one model with 82 classes: the 80 the current model knows plus
`pen` and `flower`. Training on Kaggle mixes a random COCO 2017 subset (sizes
are `training.yaml` knobs) with the user's frames. On the user's frames, every
object of the 80 base classes is labelled automatically by the current model,
run locally before upload; an automatic box that overlaps a hand-drawn box above
an IoU knob is dropped. The new model is plugged in by one `model.weights` line,
and the old model stays in `models/` as the fallback.

## Why

Considered and rejected:

- **A model with only the two new classes.** Loses all 80 COCO classes, so the
  existing rules, whitelist and handlers stop working with it.
- **Two models in sequence (stock + custom).** Doubles inference time on a CPU
  that already runs at the edge of the budget (and the Raspberry Pi of phase 5
  is slower), and needs a second detector path through `core/` — an abstraction
  around model choice the architecture forbids.
- **Training on the user's frames without COCO.** The head for the 80 classes
  forgets them within a few epochs (catastrophic forgetting).
- **Training on COCO + user frames without pseudo-labels.** People, phones and
  cups on the user's frames are unlabelled, so the model is taught they are
  background — exactly in the room it will run in.
- **Keeping pseudo-boxes that overlap a hand box.** The base model tends to call
  a pen a `knife` or `toothbrush`; keeping that box teaches two classes for one
  object.

## Consequences

Accuracy on the 80 COCO classes may drop after fine-tuning. It is measured, not
assumed: the training run reports mAP50 on the COCO subset before and after,
next to the per-class mAP50 on the user's validation frames. If the drop is
unacceptable, the answer is a larger COCO subset or more epochs, not a second
model.

Pseudo-labels carry the base model's mistakes into the training set: a missed
person stays background, a false box stays a false label. The threshold is a
knob; there is no review step for automatic boxes.

Each training run needs a COCO dataset on Kaggle and a longer GPU session than
two classes alone would.

Expensive to reverse: switching to the two-model design later means new
runtime code, not a config line.
