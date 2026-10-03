# Custom classes: teaching the model `pen` and `flower`

This guide takes you from a phone video of your desk to a model that finds a
pen and a flower next to the 80 classes it already knows, switched on with one
line of `config.yaml`. Every step is one command and one line of *why*.
The user's steps in Ukrainian: [README.uk.md](README.uk.md).

Everything runs on this laptop and offline, except four named steps:
`pip install`, `label_studio.py setup` (pip), the `kaggle_run.py` subcommands
that talk to Kaggle, and the training notebook on Kaggle itself. Every Kaggle
subcommand prints its plan and sends nothing until you add `--yes`.

All commands run from the project root (`D:\Projects\Vision`).

## The path of the data

```
your video ─► extract_frames ─► data/training/frames/<video>/*.jpg
                                        │
              Label Studio (own venv, local) ◄┘  draw pen/flower boxes;
                    │                           a frame with nothing = negative
                    ▼ export "YOLO"
        (optional) rough model ─► prelabel ─► boxes ready to correct in Label Studio
                    ▼
build_dataset: + the current model labels its 80 classes on your frames,
               + (optional) a ready-made dataset, ≤ 20 % of the set,
               train/val split per video, data.yaml with 82 names
                    ▼
kaggle_run upload ─► kaggle_run train ─► Kaggle GPU: COCO slice + your data ─► best.pt
                    ▼                                          + metrics.json
kaggle_run fetch ─► models/<name>.pt ─► evaluate ─► export_openvino ─► config.yaml
```

The new model has 82 classes: IDs 0-79 are the current model's names in the
same order, 80 = `pen`, 81 = `flower`. Your rules, `classes` whitelist and
`handlers.py` stay valid. The new classes come from `classes` in
`training/training.yaml`, where every other training number lives too.

## What you need

- **The training extras**, once: `venv\Scripts\python -m pip install -r requirements-training.txt`
  -- installs the `kaggle` command-line tool into the project venv.
- **A Kaggle account** (free): register at https://www.kaggle.com.
- **A verified phone number** on that account (Settings, Phone verification) --
  without it Kaggle turns on neither the GPU nor internet access for a notebook,
  and the training notebook needs both.
- **An API token**: on kaggle.com, Settings, API, *Create New Token*. Put the
  downloaded `kaggle.json` at `%USERPROFILE%\.kaggle\kaggle.json` yourself.
  The key never goes through the agent: `kaggle_run.py check` only checks that
  the file exists and never reads it.
- **Your Kaggle login** in `training/training.yaml`: `kaggle.username: "yourname"`
  -- the name of your private dataset and notebook are built from it.

Check it all, locally, sending nothing:

```
venv\Scripts\python training\kaggle_run.py check
```

It prints `ok`, or one sentence per missing piece.

## 1. Shoot

*Why:* the model learns exactly the scene it is shown, so shoot what the
camera will see.

- **Real conditions**: your desk, your light (day and lamp), the distance and
  height of the camera that will run the model. Shoot with the webcam itself
  if you can; a phone works too.
- **The pen is small.** At 640 px a pen across the desk is ~40 px long; shoot
  it at that size, not only close up.
- **Variety**: several pens and flowers, lying, standing, in a hand, half
  covered, from different sides.
- **Negatives**: a good share of frames with *no* pen and no flower -- the
  empty desk, a pencil, a marker, a phone. They teach the model what a pen is
  *not*. `build_dataset` warns when they are below
  `dataset.min_negative_fraction` (10 %).
- **About 10 minutes of video** in total, in several clips. At 30 fps and every
  20th frame (`frames.step`) that is ~900 frames (`frames.target_total`).

Before shooting, check whether a ready-made dataset helps (section 3).

## 2. Cut the video into frames

*Why:* consecutive frames are near-duplicates; every 20th keeps the variety
without the repetition.

```
venv\Scripts\python training\extract_frames.py --video D:\clips\desk1.mp4
```

Writes `data/training/frames/desk1/desk1_000000.jpg`, `..._000020.jpg`, ... and
ends with `total M frames in data/training/frames (target ~900)`. Run it once
per clip. It refuses a folder that already has frames unless `--force`.

## 3. Ready-made datasets (optional)

*Why:* a few hundred already-labelled images add variety you did not shoot.
`build_dataset --extra DIR` mixes one in as at most `dataset.internet_fraction`
(20 %) of the whole set. Your own frames stay the core: they are your scene.

Checked on 2026-10-03. Roboflow pages block automated reading, so the numbers
below are the ones Roboflow Universe lists in its search results. Open the page,
look at the images and the class names, and check the license before you use one.

| Class | Dataset | Link | License | Images |
|---|---|---|---|---|
| pen | "pen" by Yoro | https://universe.roboflow.com/yoro/pen-8rexy | CC BY 4.0 | 55 |
| pen | "Pen" by Zainab Aldhanhani | https://universe.roboflow.com/zainab-aldhanhani/pen-nsayu | CC BY 4.0 | 53 |
| flower | "Flower Detection" by Orbit Final Project | https://universe.roboflow.com/orbit-final-project/flower-detection-fscsr | CC BY 4.0 | 3336 |
| flower | "flower detection" by flower | https://universe.roboflow.com/flower-42dyl/flower-detection-hiutj | CC BY 4.0 | 182 |
| pen, flower | Open Images V7 (Google), classes `Pen` and `Flower` | https://storage.googleapis.com/openimages/web/index.html | images CC BY 2.0 (as the FiftyOne zoo page lists it) | 600 classes, ~1.9 M images overall; the per-class counts were not checked |

**Roboflow Universe**: on the dataset page, *Download Dataset*, format
**YOLOv8** (or any YOLO format), *download zip*, unzip somewhere, e.g.
`D:\datasets\pens`. It has a `data.yaml` with the class names, which
`--extra` reads (names match without regard to case; other classes are dropped).

**Open Images V7** through FiftyOne, which downloads only the images holding the
classes you ask for. FiftyOne goes into `venv-labelstudio` (section 4 creates it),
never into the project venv:

```
venv-labelstudio\Scripts\python -m pip install fiftyone
```

If pip reports a conflict with Label Studio's pins, put FiftyOne into a venv of
its own instead (`py -3.11 -m venv venv-fiftyone`); nothing else changes.
Save this as `data\training\openimages.py` and run it with
`venv-labelstudio\Scripts\python data\training\openimages.py`:

```python
from pathlib import Path

import fiftyone as fo
import fiftyone.zoo as foz

CLASSES = ["Pen", "Flower"]
OUT = Path("data/training/openimages")

dataset = foz.load_zoo_dataset(
    "open-images-v7", split="train", label_types=["detections"],
    classes=CLASSES, max_samples=500, shuffle=True, seed=0)
dataset.export(export_dir=str(OUT), dataset_type=fo.types.YOLOv5Dataset,
               label_field="ground_truth", split="train", classes=CLASSES)
(OUT / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
```

The last line writes the `classes.txt` that `--extra` reads, in the order the
export numbered the classes. Then: `--extra data\training\openimages`.

**Why not images scraped from a search engine**: they come without boxes, so
they save no labelling; they are product shots on white backgrounds, not your
desk; their licenses are unknown; and they repeat each other.

## 4. Label in Label Studio

*Why:* boxes drawn by hand are what the model learns from. Label Studio runs
on this machine, in its own venv: it brings Django and its own version pins,
which could break the project's ultralytics/openvino.

Install it once (online, pip; skipped when `venv-labelstudio\Scripts\label-studio.exe`
is already there):

```
venv\Scripts\python training\label_studio.py setup
```

Start it (you, not the agent -- it is a server on your machine; Ctrl+C stops it):

```
venv\Scripts\python training\label_studio.py start
```

- It listens on `127.0.0.1` only (`--internal-host 127.0.0.1`), so nothing
  outside this laptop can reach it; your browser opens http://localhost:8080.
- It sets `LABEL_STUDIO_COLLECT_ANALYTICS=false` (usage analytics) and
  `LABEL_STUDIO_LATEST_VERSION_CHECK=false` (the PyPI version check). Sentry
  error reporting needs a DSN, which the open-source build does not have, so
  it sends nothing.
- It serves `data/training` as local files, so frames are never uploaded anywhere.

Print the labeling interface for `training.classes`:

```
venv\Scripts\python training\label_studio.py config
```

In the browser (the clicks below -- local-files storage here and deleting the
empty tasks in section 5 -- are written from Label Studio's documentation and
get checked against the first real project):

1. Sign up (a local account, stored on this machine), *Create Project*.
2. *Labeling Setup*, *Custom template*, *Code*: paste what `config` printed; Save.
3. Project *Settings*, *Cloud Storage*, *Add Source Storage*, type **Local
   files**, absolute path of one frames folder, e.g.
   `D:\Projects\Vision\data\training\frames\desk1`; tick *Treat every bucket
   object as a source file*; *Add Storage*, then *Sync Storage*. One storage
   per clip. The path must be inside `data\training`.
4. Label: draw a rectangle per pen / flower, tight to the object. A frame with
   neither: *Submit* with no boxes -- it becomes a negative.
5. *Export*, format **YOLO**, save the zip into `data\training\exports\`,
   e.g. `data\training\exports\all.zip`.

## 5. Rough model and pre-labelling (optional, saves most of the clicking)

*Why:* label ~50 frames by hand, train a quick 2-class model on them, and let
it draw the boxes on the rest; you only correct them.

1. Label ~50 frames (step 4), export as `data\training\exports\first50.zip`.
2. Build the rough set -- only the labelled frames, only `pen`/`flower`, no
   model labels, no `--extra`:
   ```
   venv\Scripts\python training\build_dataset.py --export data\training\exports\first50.zip --name rough --rough
   ```
3. Upload **that** build, then train in rough mode (`rough.epochs`, no COCO).
   `train` trains on whatever build was uploaded last, and reads the mode from
   its `manifest.json`, so `train --rough` comes right after `upload --build rough`:
   ```
   venv\Scripts\python training\kaggle_run.py upload --build rough --yes
   venv\Scripts\python training\kaggle_run.py train --rough --yes
   venv\Scripts\python training\kaggle_run.py status --yes
   venv\Scripts\python training\kaggle_run.py fetch --name rough --yes
   ```
4. Pre-label every frame not in the export (works only with frames under `data\training`):
   ```
   venv\Scripts\python training\prelabel.py --weights models\rough.pt --frames data\training\frames --skip-labelled data\training\exports\first50.zip
   ```
   This writes `data\training\tasks.json`.
5. In Label Studio, so each frame is one task: Data Manager, filter
   *Annotations = 0*, select all, *Actions*, *Delete tasks* (only the tasks go,
   not the image files). Then *Import* `data\training\tasks.json`. The model's
   boxes appear as predictions: check each frame, fix or delete wrong boxes,
   add missed ones, *Submit*.
6. Export everything (step 4.5) as `data\training\exports\all.zip`.

## 6. Build the dataset

Keep the frames in `data\training\frames` while you build: Label Studio may put a
prefix such as `17-` in front of a frame's name, and the build tells a prefix from
a clip named like `20261003-desk` by looking at the frames on disk. Without them
it goes by the name alone and may read a dated clip name as a prefix.

*Why:* one folder that holds everything the training needs, checked before it
is uploaded.

```
venv\Scripts\python training\build_dataset.py --export data\training\exports\all.zip --name first
venv\Scripts\python training\build_dataset.py --export data\training\exports\all.zip --name first --extra D:\datasets\pens
```

- Writes `data/training/build/first/`: `images/` and `labels/` (`train`, `val`),
  `data.yaml` with 82 names, a copy of `training.yaml`, the base weights
  (`training.base_weights`), `manifest.json`.
- The current model (`model.weights` in `config.yaml`) labels its own 80
  classes on your frames at `dataset.pseudo_conf` -- otherwise the people on
  your frames would teach the new model that a person is background. A model
  box overlapping your box by `dataset.pseudo_iou_drop` IoU or more is dropped,
  so a pen is never also learnt as a knife.
- Images from `--extra` get no such model labels (a person on them is
  background), and the "is there any pen or flower box" check counts only your
  own frames.
- Validation is the last 20 % (`dataset.val_fraction`) of every clip, as one
  block, so near-duplicate frames never sit on both sides.
- It prints the box counts and the share of negatives; an existing build is
  refused unless `--force`.

## 7. Train on Kaggle

*Why:* a free Kaggle GPU trains many times faster than this laptop's CPU.

```
venv\Scripts\python training\kaggle_run.py upload --build first
venv\Scripts\python training\kaggle_run.py upload --build first --yes
venv\Scripts\python training\kaggle_run.py train --yes
venv\Scripts\python training\kaggle_run.py status --yes
venv\Scripts\python training\kaggle_run.py fetch --name pen --yes
```

- Without `--yes` every one of `upload`, `train`, `status`, `fetch` prints what
  it would send where (and the size) and exits having sent nothing.
- `upload` sends the build as your **private** dataset `<username>/vision-training`
  (a new version when it exists).
- `train` pushes `training/kaggle/train.py` as a private GPU notebook
  `<username>/vision-train`, reading your dataset and the public COCO 2017
  dataset `kaggle.coco_dataset` (`awsaf49/coco-2017-dataset`). It installs
  `ultralytics==8.4.157`, mixes `coco.train_images` COCO images into training
  so the 80 classes are not forgotten, trains `train.epochs` epochs, and
  measures COCO mAP50 before and after.
- `status` shows the notebook's state; wait until it reports complete.
- `fetch` brings `best.pt` and `metrics.json` home as `models/pen.pt` and
  `models/pen.metrics.json`, prints the sha256 and the next commands; an
  existing `models/pen.pt` is kept unless `--force`.
- To use a different COCO copy: set `kaggle.coco_dataset` to its slug. The
  notebook looks under `/kaggle/input`, up to 4 folders deep, for
  `annotations/instances_train2017.json` with `train2017/` and `val2017/` beside it.

**Said plainly:** the notebook has been run locally on the CPU (one epoch, tiny
images, synthetic data, in the tests). Its behaviour on a Kaggle GPU -- the
paths under `/kaggle/input`, the pip install, the run time -- is proven only
by the first real run. If it fails, the notebook log on kaggle.com says where.

## 8. Check: is it good enough?

*Why:* `metrics.json` is measured on Kaggle; this measures on your frames, on
this CPU, side by side.

```
venv\Scripts\python training\evaluate.py --weights models\yolo26n.pt models\pen.pt --build first
venv\Scripts\python training\evaluate.py --weights models\pen.pt models\pen-s.pt --build first --imgsz 960
```

For every model: mAP50 and mAP50-95 for `pen` and `flower`, the same for
`all` classes every compared model knows (with the stock model in the list,
that is how well the 80 old classes survived), and seconds per frame. Models
with different class lists (the 2-class rough one, the stock 80, the new 82)
are scored on the same boxes by class name; `-` means the model does not know
the class, or val holds no box of it. Also look at `models/pen.metrics.json`:
`coco.base_mAP50` vs `coco.trained_mAP50`.

If the pen is weak, in this order:

1. **Shoot closer**, or more frames where the pen is small, and retrain.
2. **`imgsz: 960`**: set `train.imgsz: 960` in `training/training.yaml`,
   rebuild with `--force`, upload, train; set `model.imgsz: 960` in
   `config.yaml` and redo the export with `--force` (an OpenVINO export has one
   fixed size). Slower per frame -- `evaluate --imgsz 960` shows how much.
3. **`yolo26s`**: `base_weights: models/yolo26s.pt` in `training/training.yaml`
   (it is already in `models/`), rebuild with `--force`, upload, train, fetch
   under another name (e.g. `pen-s`), compare with `evaluate`.

## 9. Switch the app to the new model

*Why:* the app and the CLI read the model from one line.

```
venv\Scripts\python scripts\export_openvino.py --weights models/pen.pt
```

That writes `models\pen_openvino_model\`. Then in `config.yaml`:

```yaml
model:
  weights: models/pen_openvino_model   # or models/pen.pt for the PyTorch model
classes:          # the whitelist: add the new names, or empty it for all 82
  - person
  - pen
  - flower
```

A rule in `rules.yaml` for the new class:

```yaml
  - name: pen_appeared
    when: appeared
    class: pen
    do: [log, save_frame]
```

The thresholds (`model.conf`, `conf_debug`, the slider) work as before.

**Going back** to the old model is the same line:
`weights: models/yolo26n_openvino_model`, and `pen`/`flower` out of `classes`
(the old model does not know them, and an unknown whitelist name is an error).
The old model is never overwritten.

## For the agent

The exact order for the session where the user brings the data. Steps marked
**[ask]** need the user's yes in chat first; show the plan line the command
printed without `--yes`. The agent never runs `label_studio.py start`, never
opens a camera, never launches `app.py` (except `--help`), and never reads or
asks for `kaggle.json`.

1. `venv\Scripts\python training\kaggle_run.py check` -- each sentence it prints
   is a task for the user (install extras **[ask]**, account, phone, token file,
   `kaggle.username` in `training/training.yaml`).
2. For each clip the user names: `venv\Scripts\python training\extract_frames.py --video <path>`.
   Report the total against the target.
3. The user labels in Label Studio (section 4) and puts the export zip into
   `data\training\exports\`. Wait for it.
4. Optional rough path (section 5): `build_dataset.py --export <first50.zip> --name rough --rough`;
   `kaggle_run.py upload --build rough` → **[ask]** → `--yes`;
   `kaggle_run.py train --rough` → **[ask]** → `--yes`;
   `kaggle_run.py status --yes` until complete (**[ask]** once for polling);
   `kaggle_run.py fetch --name rough` → **[ask]** → `--yes`;
   `prelabel.py --weights models\rough.pt --frames data\training\frames --skip-labelled <first50.zip>`;
   the user deletes the empty tasks, imports `tasks.json`, corrects, exports `all.zip`.
5. `venv\Scripts\python training\build_dataset.py --export <all.zip> --name first`
   (add `--extra <dir>` if the user downloaded a dataset). Show the counts and the
   negatives line.
6. `kaggle_run.py upload --build first` → **[ask]** → `--yes`.
7. `kaggle_run.py train` → **[ask]** → `--yes`. The run time is unknown until
   the first real run.
8. `kaggle_run.py status --yes` until it reports complete; on an error status,
   the user opens the notebook log on kaggle.com.
9. `kaggle_run.py fetch --name pen` → **[ask]** → `--yes`.
10. `venv\Scripts\python training\evaluate.py --weights models\yolo26n.pt models\pen.pt --build first`;
    show the table and `models\pen.metrics.json`. If the pen is weak, propose
    section 8's options; each retrain repeats 5-9 **[ask]**.
11. `venv\Scripts\python scripts\export_openvino.py --weights models/pen.pt`.
12. **[ask]** before editing `config.yaml` (`model.weights`, `classes`) and
    `rules.yaml`; the user runs the app or `detect.py --source camera:0` to
    see it live.

## Troubleshooting

| Message | Fix |
|---|---|
| `kaggle is not installed -- run: ...` | `venv\Scripts\python -m pip install -r requirements-training.txt` |
| `no Kaggle API key at ...` | create the token (What you need) and put the file there |
| `set training.kaggle.username in training/training.yaml` | your Kaggle login, in quotes |
| `run training/label_studio.py setup first` | `venv-labelstudio` is missing; run `setup` |
| `<folder> already has files; pass --force ...` | frames of that clip exist; `--force` replaces same-named frames |
| `the export has classes not in training.classes: ...` | a label name in Label Studio differs from `training.classes`; fix the labeling config, relabel or rename, export again |
| `the export has no pen or flower box at all; ...` | the export holds only empty frames; label some objects first |
| `warning: negatives are below dataset.min_negative_fraction ...` | add frames of the scene without the objects |
| `warning: the extra dataset has only N images ...` | all of it is used; below 20 %, which is fine |
| `the kernel output has no best.pt; is the run finished?` | `status --yes` first; fetch after `complete` |
| `<weights> knows none of the classes of the build ...` (evaluate) | that model shares no class name with the build |
| `unknown class names in config: ...` (app, `detect.py`) | `classes` in `config.yaml` names a class the model in `model.weights` lacks |
| `run scripts/export_openvino.py first` | `model.weights` names an OpenVINO folder not exported yet |
| Kaggle notebook fails without a GPU | the phone number is not verified on the account |
