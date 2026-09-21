# Vision

Put a photo in front of the machine and find out what is in it and, more
importantly, *where*: not "somewhere over there" but a number -- how far the
centre of each object sits from the centre of the frame, in pixels and as a
fraction of the frame.

One command draws the overlay, writes an annotated JPG and a JSON file, and
prints one line per object. That offset is what a pan-tilt camera will be
steered with later; phase 1 exists to prove it is computed correctly on your
own photos.

Everything runs offline on the CPU. The network is touched in exactly two
places: `pip install` and `scripts/fetch_models.py`. Nothing else in the
project is allowed to reach it.

- Python 3.11 in a project-local `venv\`
- YOLO26 through `ultralytics`, weights loaded from an explicit local path
- Every number the project uses lives in `config.yaml` and nowhere else

## Install

Python 3.11 has to be present; `py -3.11 --version` should answer. Then, from
the project root:

```
py -3.11 -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python -c "import torch, cv2, ultralytics"
```

The last command printing nothing is the whole success criterion.

Then fetch the weights and the stock test photo. This is the one online step,
and the last one:

```
venv\Scripts\python scripts\fetch_models.py
```

It writes `models\yolo26n.pt`, `models\yolo26s.pt`,
`data\test_images\bus.jpg` and `models\checksums.txt`, and prints a summary.
Running it again reports `skip` for whatever is already on disk and does not
touch the network at all.

Tests:

```
venv\Scripts\python -m pytest -q
```

## Run

One photo:

```
venv\Scripts\python detect.py --source data/test_images/bus.jpg
```

A window opens with the overlay: an amber box per object, a red crosshair at
the centre of the frame, a small green cross at the centre of each object and
`dx / dy` printed inside the box. Press any key for the next frame, `q` or
`Esc` to stop. The console prints one line per object, and `out\` gets
`bus_annotated.jpg` and `bus.json`.

A whole folder, in file-name order:

```
venv\Scripts\python detect.py --source data/test_images
```

No graphical session, or you just want the files:

```
venv\Scripts\python detect.py --source data/test_images/bus.jpg --no-window
```

All the flags together:

```
venv\Scripts\python detect.py --source data/test_images/bus.jpg --no-window --conf 0.3 --classes person "cell phone" --color
```

| Flag | Does |
|---|---|
| `--source PATH` | an image file or a folder of images (required) |
| `--conf FLOAT` | confidence threshold for drawing and printing, `0..1`; overrides `model.conf`, and pulls `model.conf_debug` down with it when you set it lower, because nothing under `conf_debug` ever leaves the model |
| `--classes NAME [NAME ...]` | class whitelist; overrides the `classes` list in the config |
| `--color` | name the dominant colour of each drawn object (loads scikit-learn, so it is slower) |
| `--no-window` | skip the preview window; the files are still written |

A flag beats the config file, the config file beats nothing: there is no third
level of defaults anywhere.

Seconds per frame on this machine:

```
venv\Scripts\python bench.py --source data/test_images/bus.jpg --runs 5
```

The first passes are discarded (`bench.warmup`): the first inference is always
the slowest, and averaging it in makes the machine look worse than it is.

Frames from the webcam, saved into `data\test_images\`. The camera is *asked*
for `capture.width` x `capture.height` -- a driver is free to hand back the
nearest size it supports -- so each line prints the size actually saved:

```
venv\Scripts\python scripts\grab.py --camera 0 --count 5
```

Point `detect.py --source data/test_images` at the folder afterwards.

## Config

`config.yaml` is the single source of every number, threshold and path. There
are no defaults in the code: a missing key is an error naming the key, not a
value quietly filled in somewhere. Adding a knob means adding it to
`config.yaml` and to the schema in `core/config.py`.

| Key | Meaning |
|---|---|
| `model.weights` | path to the `.pt` file, resolved from the working directory |
| `model.imgsz` | inference size; 640 is what YOLO26 was trained at |
| `model.conf` | threshold for drawing, printing and events |
| `model.conf_debug` | lower threshold; what lands between the two is written to the JSON with `"debug": true` and is never drawn or printed. The band is empty when the two thresholds meet, so `--conf 0.25` or lower leaves no `"debug": true` entry in the file at all -- the flag drags `conf_debug` down with it |
| `classes` | class whitelist; an empty list means all 80 COCO classes |
| `display.show_labels` | class name and score above each box |
| `display.show_offsets` | `dx / dy` inside each box |
| `display.crosshair` | red crosshair at the centre of the frame |
| `display.center_line` | line from the frame centre to each object centre |
| `output.save_json` | write `out\<name>.json` |
| `output.save_image` | write `out\<name>_annotated.jpg` |
| `output.dir` | where both of them go |
| `capture.width`, `capture.height` | resolution `scripts/grab.py` asks the camera for |
| `capture.camera` | camera index it opens by default |
| `capture.count` | frames it saves per run |
| `capture.interval` | seconds between saved frames |
| `bench.runs` | measured passes in `bench.py` |
| `bench.warmup` | passes discarded before measuring |

Switching to the bigger model is one line -- `model.weights:
models/yolo26s.pt` -- and nothing else changes.

A repeated run overwrites what is in `out\`: this is a debugging tool, not an
archive.

## Troubleshooting

**`FileNotFoundError: run scripts/fetch_models.py first`** -- the weights are
not on disk. Run that script. Nothing downloads weights on its own: a model
that silently fetches itself is the one thing this project refuses to do.

**`source not found: ...` or `not an image: ...`, exit code 2** -- the path is
wrong or the extension is not one OpenCV decodes (`.jpg`, `.jpeg`, `.png`,
`.bmp`, `.webp`, `.tif`, `.tiff`).

**`config key ... must be ...` or `missing config key: ...`** -- `config.yaml`
is malformed and the message names the key. There is no fallback value.

**`camera 0 is not available or is in use by another program`, exit code 2** --
something else holds the webcam (a video call, the Camera app), or the index is
wrong. Close the other program, or try `--camera 1`.

**The window does not open, or you are on a machine with no display** -- use
`--no-window`. If `cv2.imshow` fails anyway, the run says so once on stderr and
carries on writing files.

**A non-Latin file name comes out unreadable** -- the console code page cannot
show it, and what you see depends on how far the run got. A detection run
prints `Ð°Ð²Ñ‚Ð¾Ð±ÑƒÑ: 4 detections`: those are the UTF-8 bytes of the real
name, drawn with a legacy code page. A usage error thrown before the model
loads prints `source not found: data\test_images\\u0444ото.jpg`
instead, with the characters escaped. Neither is a failure and neither stops
the run: the files on disk carry the real name, and `out\` holds them spelled
correctly. `chcp 65001` before the run, or a terminal already set to UTF-8,
prints both properly.

**`torch.cuda.is_available()` is `False`** -- expected. The installed wheels
are CPU-only and the whole project is built for a machine without CUDA.

**The first run takes several seconds** -- the model loads and the first
inference initialises its buffers. `bench.py` discards exactly this, which is
why its numbers are much lower than what the first run feels like.
