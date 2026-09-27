# Vision

Put a photo in front of the machine and find out what is in it and, more
importantly, *where*: not "somewhere over there" but a number -- how far the
centre of each object sits from the centre of the frame, in pixels and as a
fraction of the frame.

One command draws the overlay, writes an annotated JPG and a JSON file, and
prints one line per object. That offset is what a pan-tilt camera will be
steered with later; phase 1 exists to prove it is computed correctly on your
own photos.

Phase 2 does the same on a video file or a live webcam: every object keeps a
number from frame to frame, one of them is the *target* (the nearest to the
centre, or the one you click), and `rules.yaml` turns "a person appeared" or
"a phone entered the door zone" into a printed line, a saved frame or a call
into your own Python function.

Everything runs offline on the CPU. The network is touched in exactly two
places: `pip install` and `scripts/fetch_models.py`. Nothing else in the
project is allowed to reach it -- including Ultralytics, whose usage analytics
`core/detector.py` switches off before the library is imported, so a fresh
clone is offline on any machine without anything being configured by hand.

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

Two packages in `requirements.txt` are there for phase 2:

- `lap` -- the assignment solver ByteTrack uses to match boxes between frames.
  Without it Ultralytics tries to install it at run time, which this project
  forbids (no network after install).
- `openvino==2026.3.1` -- Intel's CPU inference runtime, for the faster model
  format below. It is pinned: 2026.4.0 sees this laptop's integrated GPU,
  Ultralytics then picks the GPU on its own and the process crashes
  (`0xC0000005`) while compiling for it. 2026.3.1 stays on the CPU.

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
| `--source PATH` | an image, a folder of images, a video file, or `camera:N` (required) |
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

## Video and webcam

A video file (`.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.m4v`):

```
venv\Scripts\python detect.py --source clip.mp4
```

The webcam (`camera:0` is the first one; a bare `0` works too):

```
venv\Scripts\python detect.py --source camera:0
```

The window plays live. `q` or `Esc` stops, and so does Ctrl+C in the
terminal; a video file also stops on its own at the end. With `--no-window` a
file runs to the end and a camera runs until Ctrl+C. `--conf`, `--classes` and
`--color` work as on photos (`--color` on every frame is slow).

What you see on each frame:

- `#7` in every label -- the track number. ByteTrack keeps it on the same
  object across frames (why ByteTrack: no extra model to download, and it uses
  the low-confidence boxes to keep a track alive through a dim frame). A new
  object gets its number from its second frame on.
- The **target**: a thick magenta box marked `TARGET`. Without a click it is
  the tracked object nearest the centre of the frame.
- **Left-click a box to lock the target onto it**, even when something else is
  closer to the centre. Click empty space to release the lock. If the locked
  object leaves the frame the target reads `lost` and nothing else is picked
  up; after `tracker.track_buffer` frames the lock is dropped.
- The top line: `target #7 person  dx +120 dy -40  ->  12.3 FPS` -- the target,
  the arrow a pan-tilt head would turn along (`core/aim.py`, a stub for now),
  and the processing speed.

The console prints nothing per frame -- only rule events (below) and one
summary line at the end: `49 frames, 6 events, wrote out\clip.jsonl,
out\clip_annotated.mp4`. Warnings and errors go to stderr.

Files written to `out\`:

| File | When | Holds |
|---|---|---|
| `<name>.jsonl` | `output.save_json` | one JSON line per frame: `source`, `index`, `time` (seconds from the start), `target` (`{"track_id", "locked", "lost"}` or `null`), `detections` with `track_id`; near-misses carry `"debug": true` |
| `<name>_annotated.mp4` | `output.save_image`, video files only | the overlay at the source's frame rate |
| `events\<name>_<rule>_<frame>.jpg` | a rule's `save_frame` action | the annotated frame the rule fired on |

JSON Lines rather than one JSON file: each line is flushed as soon as the frame
is done, so a run stopped with Ctrl+C or by a camera failure still leaves every
frame up to the last one. A webcam writes no video -- it would grow without
limit -- and its files are named `camera_0.*`.

## Desktop app

Everything `detect.py` does, in one window:

```
venv\Scripts\python app.py
```

or with something opened as soon as the model is in:

```
venv\Scripts\python app.py --source data/test_images/bus.jpg
```

`--source` takes the same values as in `detect.py`: a photo, a folder, a video
file or `camera:N`. The window opens at once and the model loads in the
background; until it is in, the status bar says `Loading model…` and the open
buttons are greyed out. A broken `config.yaml` is one sentence in the terminal
and no window, exactly as with `detect.py`.

Where things are:

- **Top row** -- `Open file…` (a photo or a video), `Open folder…`, the camera
  number (starts at `capture.camera`) and `Open camera`, then `Stop`, `Pause`
  (video files only; the space bar does the same) and `◀ Prev` / `Next ▶` with
  `3 / 12` for a folder. Stepping back through a folder does not run the model
  again.
- **Left** -- the frame with the same overlay `detect.py` writes into
  `_annotated.*`, fitted to the window. Click a box to lock the target onto it,
  click empty space to release it -- on a paused video too. Under the frame,
  the `Confidence` slider.
- **Middle** -- `Objects`: one row per drawn object (`#id`, class, conf, `dx`,
  `dy`, `dx %`, `dy %`, and colour when it is on), the target row in magenta
  and marked `TARGET`; under it, how many near-misses are hidden (they are in
  the files only). Then `Events`: the same lines `detect.py` prints for
  `rules.yaml`, newest at the bottom.
- **Right** -- `Settings`: model, `imgsz`, classes, colour, centre line, and
  `Save to config.yaml`.
- **Bottom** -- the status bar: source, frame `i / N`, FPS, near-misses; at the
  end of a video the same summary line `detect.py` prints.

The **Confidence slider** runs from `model.conf_debug` up to `1.00` in steps of
`0.01` and starts at `model.conf`. It cannot go lower: the model runs at
`conf_debug`, so nothing below it exists. On a photo the boxes are redrawn at
once without running the model again, and `out\<name>.json` /
`<name>_annotated.jpg` are rewritten to match the screen when you let go of the
slider. Moving it with the keyboard or the mouse wheel rewrites them too, on
every step -- not only releasing a drag. On a video or a webcam the new
threshold applies from the next frame -- boxes, list, target, rules and
ByteTrack's own thresholds -- and track numbers carry on.

**Settings apply at once**, to this session only; there is no Apply button.
The model list shows the `*.pt` files and `*_openvino_model` folders in
`models\`. Picking another model, or another `imgsz` (applied on Enter or when
the field loses focus), reloads the model in the background -- the status bar
says `Loading model…`, a running video waits and carries on with the same
tracks, a photo is detected again. A model that will not load is said in a
message box, and the previous one keeps working and comes back in the list.
With an OpenVINO model `imgsz` is greyed out: the export fixed it (re-run
`scripts\export_openvino.py --force` to change it). Classes are ticked from the
loaded model's names; no tick means all of them. A class name the model does
not know (a typo in `config.yaml`) stays in the list, marked; ticking classes
while it is there gives `unknown class names in config: …` and the previous
selection comes back. The colour tick is `--color` (slow, it loads
scikit-learn) and is saved as `display.color`; `detect.py` names colours when
either the flag or that key is on.

**Save to config.yaml** writes only what differs from the file, out of
`model.weights`, `model.imgsz`, `model.conf` (the slider), `classes`,
`display.center_line` and `display.color`. The right end of the status bar says
`Saved: model.conf, classes` or `Nothing to save` for a few seconds, even while
a video runs. Comments, commented-out lines and
key order stay as they were; the result is checked by loading it before it
replaces the file, and on any error the file is left untouched and the
sentence is shown.

**Files** go to `out\` exactly as with `detect.py` on the same source: a photo
writes `<name>.json` and `<name>_annotated.jpg`, a video `<name>.jsonl`,
`<name>_annotated.mp4` and event frames, a webcam `camera_N.jsonl` and event
frames. `rules.yaml` and `handlers.py` work the same way, and a broken
`rules.yaml` is a message before the camera is switched on.

**The camera is released** by `Stop`, by opening another source, or by closing
the window -- the window waits for the processing thread to finish before it
goes. A busy camera (`camera N is not available or busy`), one that stops
mid-run, a file that will not open or cannot be written: each is one sentence
in a message box, and the app stays open for the next source.

## Rules

`rules.yaml` (path set by `rules.file` in `config.yaml`) says what counts as
an event on a video or webcam. Photos ignore it: a single frame has no "before"
to compare with.

```yaml
debounce:
  confirm_frames: 3     # consecutive frames before a change counts
  cooldown: 5.0         # seconds a (rule, object) pair stays quiet after firing
zones:
  door: [0.0, 0.0, 0.3, 1.0]   # x1, y1, x2, y2 as fractions of the frame
rules:
  - name: person_appeared
    when: appeared
    class: person       # optional; leave it out for any class
    do: [log]
  - name: phone_at_door
    when: entered
    zone: door
    class: cell phone
    do: [log, save_frame, {call: on_phone}]
```

Conditions (`when`), each firing once per tracked object:

| `when` | Fires when |
|---|---|
| `appeared` | a new object has been seen `confirm_frames` frames in a row |
| `disappeared` | a known object has been missing `confirm_frames` frames in a row |
| `present` | an object has stayed in view `seconds: N` seconds (stream time, not wall clock) |
| `entered` | an object's centre has been inside `zone:` for `confirm_frames` frames after being outside it; an object first seen inside the zone counts too |

Actions (`do`), in the order listed:

| Action | Does |
|---|---|
| `log` | prints `[00:12.4] person_appeared  person #7 0.83  dx +120 dy -40` |
| `save_frame` | writes the annotated frame to `out\events\` |
| `{call: name}` | calls the function `name` from `handlers.py` |

Why the debounce: the model's confidence wobbles between frames, and an object
hovering at 0.49 / 0.51 would otherwise "appear" and "disappear" dozens of
times a second. `confirm_frames` makes a change prove itself first, and
`cooldown` keeps the same rule quiet on the same object for a while after it
fired. Zones are fractions of the frame (`0..1`), not pixels, so one file works
for a 640x480 webcam and a 4K video alike. Rules only see what is drawn -- at
or above `model.conf`, with a track number.

A broken `rules.yaml` stops the run with one sentence naming the rule and key,
exit code 2.

## Your own code: `handlers.py`

`handlers.py` in the project root holds the functions rules can call. Register
one with `@on_detect` and call it by its function name:

```python
from core.events import on_detect

@on_detect(cls="cell phone")    # leave out cls to accept every class
def on_phone(detection):
    print(f"phone #{detection.track_id} at dx {detection.dx:+d}")
```

```yaml
    do: [{call: on_phone}]
```

The function gets the `Detection` that made the rule fire (`cls_name`, `conf`,
`bbox`, `center`, `dx`, `dy`, `dx_pct`, `dy_pct`, `track_id`). A rule calling a
name `handlers.py` does not define stops the run at start-up: `unknown handler
in rules.yaml: <name>`, exit code 2. A rule whose `class` the handler's `cls`
can never match gets one warning at start-up. A function that raises is logged
and skipped. On a stream your functions run only through rules -- never once
per frame -- so they fire at the rate of events, not at 25 times a second.

## Faster inference: OpenVINO

OpenVINO is Intel's runtime for running a model on an Intel CPU. Export the
model once (offline, no download):

```
venv\Scripts\python scripts\export_openvino.py
```

It writes `models\yolo26n_openvino_model\`; running it again prints `skip`,
`--force` rewrites it, `--weights models/yolo26s.pt` exports the other model.
Then switch with one line of `config.yaml`:

```yaml
model:
  weights: models/yolo26n_openvino_model
```

Nothing else changes. Compare both on your own machine:

```
venv\Scripts\python bench.py --source data/test_images/bus.jpg --weights models/yolo26n.pt models/yolo26n_openvino_model
```

Measured on this laptop (4-core Intel U-series CPU, `bus.jpg`, 3 warm-up + 10
measured passes, openvino 2026.3.1):

| Weights | Seconds per frame | FPS |
|---|---|---|
| `yolo26n.pt` (PyTorch) | 0.0791 | 12.65 |
| `yolo26n_openvino_model` | 0.0514 | 19.45 |
| **Speed-up** | | **1.54x** |

That is less than the 2-3x `ARCHITECTURE.md` estimated: here it is about
1.5x (1.65x on a 20-pass run), and single runs vary by up to 30% on a
4-core laptop CPU. Both formats find the same four people on `bus.jpg`, with
boxes within 7 px of each other. The default stays `.pt` so a fresh clone
works without the export step.

## Config

`config.yaml` is the single source of every number, threshold and path. There
are no defaults in the code: a missing key is an error naming the key, not a
value quietly filled in somewhere. Adding a knob means adding it to
`config.yaml` and to the schema in `core/config.py`.

| Key | Meaning |
|---|---|
| `model.weights` | path to the `.pt` file or the exported OpenVINO folder, resolved from the working directory |
| `model.imgsz` | inference size; 640 is what YOLO26 was trained at |
| `model.conf` | threshold for drawing, printing and events |
| `model.conf_debug` | lower threshold; what lands between the two is written to the JSON with `"debug": true` and is never drawn or printed. The band is empty when the two thresholds meet, so `--conf 0.25` or lower leaves no `"debug": true` entry in the file at all -- the flag drags `conf_debug` down with it |
| `classes` | class whitelist; an empty list means all 80 COCO classes |
| `display.show_labels` | class name and score above each box |
| `display.show_offsets` | `dx / dy` inside each box |
| `display.crosshair` | red crosshair at the centre of the frame |
| `display.center_line` | line from the frame centre to each object centre |
| `output.save_json` | write `out\<name>.json` (photos) or `out\<name>.jsonl` (streams) |
| `output.save_image` | write `out\<name>_annotated.jpg` (photos) or `out\<name>_annotated.mp4` (video files) |
| `output.dir` | where all of them go |
| `capture.width`, `capture.height` | resolution the webcam is asked for, by `detect.py` and `scripts/grab.py`; a camera that delivers another size gets one warning |
| `capture.camera` | camera index it opens by default |
| `capture.count` | frames it saves per run |
| `capture.interval` | seconds between saved frames |
| `bench.runs` | measured passes in `bench.py` |
| `bench.warmup` | passes discarded before measuring |
| `tracker.track_buffer` | frames a vanished object keeps its track number (and a click lock) before it is forgotten |
| `tracker.match_thresh` | how closely a box must overlap a track's predicted position to continue it |
| `tracker.fuse_score` | let the detection's confidence count when matching boxes to tracks |
| `rules.file` | the rules file, resolved from the project root |

The tracker's confidence bands are not separate knobs: it follows `model.conf`
and `model.conf_debug` (and so `--conf`), which is why a near-miss can keep a
track alive but never starts one.

Switching to the bigger model is one line -- `model.weights:
models/yolo26s.pt` -- and nothing else changes.

A repeated run overwrites what is in `out\`: this is a debugging tool, not an
archive.

## Troubleshooting

**`FileNotFoundError: run scripts/fetch_models.py first`** -- the weights are
not on disk. Run that script. Nothing downloads weights on its own: a model
that silently fetches itself is the one thing this project refuses to do.

**`source not found: ...` or `not an image or video: ...`, exit code 2** -- the path is
wrong or the extension is not one OpenCV decodes (`.jpg`, `.jpeg`, `.png`,
`.bmp`, `.webp`, `.tif`, `.tiff`).

**`config key ... must be ...` or `missing config key: ...`** -- `config.yaml`
is malformed and the message names the key. There is no fallback value.

**`camera 0 is not available or busy`, exit code 2** -- something else holds
the webcam (a video call, the Camera app), or the index is wrong. Close the
other program, or try `camera:1` (`--camera 1` for `scripts/grab.py`).

**`camera 0 stopped delivering frames`, exit code 1** -- the webcam was
unplugged or taken over mid-run. The JSONL is closed and whole up to the last
frame, and the summary line still says what was written.

**`cannot open video: ...`, exit code 2** -- the file is damaged, empty or in a
codec OpenCV cannot read. FFmpeg may print a line of its own before it
(`moov atom not found`); it is the same problem.

**`run scripts/export_openvino.py first`, exit code 2** -- `model.weights`
points at an OpenVINO folder that has not been exported yet.

**`rules file not found: ...` or `rules[<name>].<key>: ...`, exit code 2** --
`rules.yaml` is missing or malformed; the message names the rule and key.

**`unknown handler in rules.yaml: <name>`, exit code 2** -- a rule says
`{call: <name>}` but `handlers.py` registers no function by that name.

**The window does not open, or you are on a machine with no display** -- use
`--no-window`. If `cv2.imshow` fails anyway, the run says so once on stderr and
carries on writing files.

**A non-Latin file name comes out unreadable** -- the console code page cannot
show it, and what you see depends on how far the run got. A detection run
prints `Ð°Ð²Ñ‚Ð¾Ð±ÑƒÑ: 4 detections`: those are the UTF-8 bytes of the real
name, drawn with a legacy code page. A usage error thrown before the model
loads prints `source not found: data\test_images\u0444\u043e\u0442\u043e.jpg`
instead, with every non-ASCII character escaped. Neither is a failure and
neither stops the run: the files on disk carry the real name, and `out\`
holds them spelled correctly. `chcp 65001` before the run, or a terminal
already set to UTF-8, prints both properly.

**`torch.cuda.is_available()` is `False`** -- expected. The installed wheels
are CPU-only and the whole project is built for a machine without CUDA.

**The first run takes several seconds** -- the model loads and the first
inference initialises its buffers. `bench.py` discards exactly this, which is
why its numbers are much lower than what the first run feels like.
