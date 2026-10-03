# 0026. Label Studio runs from its own venv inside the project

## Context

Labelling is done in Label Studio, installed with pip. It brings Django and its
own pinned versions of many packages. The project venv carries
`ultralytics==8.4.157` and `openvino==2026.3.1`, both pinned for reasons that
cost a crash to rediscover (ADR 0013). The brief says to ask before installing
anything system-wide.

## Decision

`training/label_studio.py setup` creates `venv-labelstudio` in the project root
(gitignored) and installs Label Studio there; FiftyOne, used for Open Images
downloads, goes into the same venv. The main `venv` gets only the light
`kaggle` CLI, from a separate `requirements-training.txt`; `requirements.txt` is
unchanged. Only the user starts Label Studio.

## Why

Considered and rejected:

- **Installing Label Studio into the main venv.** Its pins can move packages
  that ultralytics or openvino depend on, and the failure shows up later as a
  broken detector, not as a broken labelling tool.
- **A system-wide or `pipx` install.** A system-wide install is what the brief
  says to ask about; both put the tool outside the project, where `setup` and
  `start` cannot find it by a fixed path.
- **Docker.** One more large dependency on a laptop that has none, for a tool
  that pip installs.
- **Putting `kaggle` in the labelling venv too.** `kaggle_run.py` runs from the
  main venv and calls the CLI as a subprocess; one venv per tool is enough
  separation, two is not needed.

## Consequences

Two venvs to install and keep working; `venv-labelstudio` is large and is
rebuilt by `setup`, not by `pip install -r requirements.txt`.

Label Studio's version is whatever pip resolves at setup time unless pinned;
behaviour that phase 4 relies on (D01, the analytics switches) was checked
against one installed version and may move with a newer one.
