# 0025. The network boundary widens for training; the runtime stays offline

## Context

Until phase 4 the only networked code was `pip install` and
`scripts/fetch_models.py`; after that the project never needed the network
(ADR 0009, ADR 0012). Phase 4 cannot keep that: Label Studio and FiftyOne are
installed with pip, training happens on a Kaggle GPU, and the result has to be
downloaded back. The brief still requires the runtime to be fully offline.

## Decision

The network is allowed in exactly these places, in addition to the old two:
`training/label_studio.py setup` (pip into its own venv),
the networked subcommands of `training/kaggle_run.py` (`upload`, `train`,
`status`, `fetch`), and the training script while it runs on Kaggle. Each
networked `kaggle_run` subcommand without `--yes` prints what would be sent,
where and how big, and exits 0 having sent nothing; the agent shows that plan
to the user and waits for a yes. The Kaggle key is placed by the user; tools
check only that the file exists and never read it. Base weights travel to Kaggle
inside the dataset and Ultralytics there is pinned to the local version, so the
notebook downloads no weights. Every other `training/` step is offline, and
`core/` never imports `training/`.

## Why

Considered and rejected:

- **Training locally on the CPU.** 6–10 hours against about 15 minutes on a
  GPU; the brief rules it out.
- **Uploading through a hand-run notebook in the browser.** Keeps the agent out
  of the loop the user asked it to run, and leaves no command to repeat.
- **One `kaggle_run` call that uploads and trains without a plan step.** The
  user's frames of their own room leave the machine without the user seeing
  what goes; the yes per upload was the user's condition.
- **Letting the notebook fetch `yolo26n.pt` from Ultralytics.** A different
  file than the one tested locally, and an auto-download the project has kept
  out everywhere else.
- **Allowing `training/` to be imported from `core/` for reuse.** Brings
  networked code within reach of the inference path.

## Consequences

The user's frames leave the machine for Kaggle in a private dataset. That is a
deliberate exception to "data never leaves the machine", which still holds for
labelling.

The project depends on a Kaggle account with a verified phone number (GPU is
off without it), on Kaggle's CLI and kernel format, and on a public COCO
dataset slug on Kaggle staying available; any of these changing breaks
training, not the runtime.

The rule in `CLAUDE.md` about where the network is allowed has to be rewritten
to name the new places; a test traps sockets around the offline steps.
