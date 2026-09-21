<!-- autopilot:start -->
# Vision

Fully offline object detection on a CPU-only laptop. A still image goes in; for
every detected object the app reports class, confidence, bounding box, and how
far the object's centre sits from the centre of the frame — in pixels and as a
fraction of half the frame. That offset is what a pan-tilt camera gets steered
with in a later phase. Current scope: phases 0, 0.5 and 1.

Code, comments, log messages, README and UI strings are **English**.
Conversation with the user is Ukrainian.

## Commands

| Command | What it does |
|---|---|
| `py -3.11 -m venv venv` | create the project interpreter (Python 3.11) |
| `venv\Scripts\python -m pip install -r requirements.txt` | install dependencies |
| `venv\Scripts\python scripts\fetch_models.py` | one-time online step: weights + stock photo |
| `venv\Scripts\python detect.py --source data/test_images/bus.jpg` | detect on one image |
| `venv\Scripts\python detect.py --source data/test_images` | detect on a folder, file-name order |
| `venv\Scripts\python detect.py --source data/test_images/bus.jpg --no-window --conf 0.3 --classes person "cell phone" --color` | every flag at once |
| `venv\Scripts\python bench.py --source data/test_images/bus.jpg --runs 5` | seconds per frame and FPS |
| `venv\Scripts\python scripts\grab.py --camera 0 --count 5` | save webcam frames into `data\test_images\` |
| `venv\Scripts\python -m pytest -q` | tests (32 pass) |
| `venv\Scripts\python -m pytest -q tests\test_config.py` | one test file |

Never plain `python`: the system interpreter is 3.7.3 and must stay untouched.

## Structure

```
detect.py            phase-1 CLI; the only wiring, and the only argparse
bench.py             timing harness, warm-up discarded
config.yaml          every number, threshold and path in the project
core/                launch-agnostic modules: types, config, source, detector,
                     geometry, draw, output, events, attributes, aim
scripts/             fetch_models.py (only networked code), grab.py (webcam)
models/              *.pt + checksums.txt — gitignored, written by fetch_models
data/test_images/    inputs — gitignored
out/                 <stem>.json, <stem>_annotated.jpg — gitignored, overwritten
tests/               test_geometry, test_config, test_detector, test_detect_cli
ARCHITECTURE.md      design of record — §9 config schema is stale, see Pitfalls
README.md            user-facing install / run / config / troubleshooting
```

## Key files

- `core/types.py` — `Detection(cls_id, cls_name, conf, bbox, center, dx, dy, dx_pct, dy_pct, color=None)`
  and `Frame(image, source, index)`. Fields are a fixed contract (ARCHITECTURE.md §7);
  contract only, no logic.
- `core/config.py` — `load_config(path) -> Config`, `ConfigError(ValueError)`.
  `Config.model / .classes / .display / .output / .capture / .bench`. One rule per
  key in `_RULES` (type + range); a missing key raises naming the key, an unknown
  key only logs a warning.
- `core/source.py` — `Source(spec, cfg)` with `__iter__() -> Iterator[Frame]` and
  `__len__()`; `IMAGE_EXTENSIONS`. Single image or folder; folder order is by
  name, case-insensitive.
- `core/detector.py` — `Detector(cfg)`, `__call__(frame) -> list[Detection]`
  returning **everything from `conf_debug` upwards**, sorted by confidence
  descending. `is_debug(detection, cfg) -> bool` marks a near-miss.
  `MISSING_WEIGHTS_MESSAGE = "run scripts/fetch_models.py first"`.
- `core/geometry.py` — `offsets(bbox, frame_size) -> (center, dx, dy, dx_pct, dy_pct)`.
  Pure. Right and down positive; centre and `dx`/`dy` rounded to whole pixels.
- `core/draw.py` — `annotate(image, detections, cfg) -> np.ndarray`, always a copy.
  Takes the frame centre from `offsets((0,0,w,h),(w,h))` so the crosshair and the
  zero of `dx`/`dy` agree on odd frame sizes.
- `core/output.py` — `write_json(source, detections, cfg, debug_detections=()) -> Path|None`,
  `write_image(source, image, cfg) -> Path|None`, `print_console(source, detections)`.
  The only module in `core/` allowed to print. JSON is
  `{"source": str, "detections": [{cls_id, cls_name, conf, bbox[4], center[2], dx,
  dy, dx_pct, dy_pct, color, debug}]}` — one array, near-misses carry `"debug": true`.
- `core/events.py` — `on_detect(cls=None)` decorator, `emit(detection)`, `clear()`;
  `Handler = Callable[[Detection], None]`. A raising handler is logged and skipped.
- `core/attributes.py` — `dominant_color(image, bbox) -> str` over the palette
  red / orange / yellow / green / cyan / blue / purple / pink / brown / black /
  gray / white. `ValueError` on a degenerate box.
- `core/aim.py` — `aim(dx, dy) -> str`, an ASCII arrow. Stub seam for the servos.
- `detect.py` — `main(argv=None) -> int`, `parse_args`, `with_overrides(cfg, args)`,
  `process(frame, detector, cfg, want_color)`, `Window(enabled).show(image) -> bool`,
  `configure_console()`, `CONFIG_PATH`, `EXIT_USAGE = 2`.
- `bench.py` — `one_pass`, `measure(detector, frames, runs, warmup)`, `report`.
- `scripts/fetch_models.py` — no arguments, exit 0/1. Stages into `models\.part\`,
  verifies size floor + zip integrity, writes `models\checksums.txt`
  (`<sha256>  <path from project root>`), reports `downloaded` | `skip`.
- `scripts/grab.py` — `main(argv=None) -> int`, `open_camera` (raises `OSError` when
  the camera is missing or busy), `grab`, `IMAGES_DIR`.

## Architecture

`detect.py` is wiring and nothing else; every decision about *how* belongs to the
module it calls. One frame's path:

`load_config(CONFIG_PATH)` → `with_overrides` applies CLI flags → `Source(spec, cfg)`
yields `Frame`s → `Detector(frame)` returns every detection at or above
`conf_debug` → `detect.process` splits that one list with `is_debug` into `drawn`
and `near_miss` → optional `attributes.dominant_color` fills `Detection.color` for
the drawn ones → `draw.annotate` → `output.print_console` / `write_image` /
`write_json(..., debug_detections=near_miss)` → `events.emit` per drawn detection →
`Window.show` returns False on `q`/`Esc`.

The load-bearing boundaries:

- **`detect.py` is the only caller of `is_debug`.** `draw.py` and `output.py` are
  handed ready-made lists and know no threshold at all. Moving the split into them
  would silently start drawing and printing near-misses.
- **`core/` never learns how it was launched.** No `argparse`, and no `print`
  outside `core/output.py`. `core/` must not import from a future `ui/`.
- **One inference pass, two thresholds.** The model runs at `conf_debug`; nothing
  below that floor ever reaches this process.
- **`Source` is the only input abstraction.** Adding video, a webcam or RTSP later
  changes that module and nothing downstream — which is why `Source.__init__`
  already takes `cfg` (for `capture.width/height`) it does not yet use.
- `bench.py` and `scripts/grab.py` import `configure_console`, `CONFIG_PATH` and
  `EXIT_USAGE` from `detect.py`, so the console trap is closed in one place.

## Code conventions

- **No number is a constant in code if a user would ever turn it.** Those live in
  `config.yaml`, and there are no defaults anywhere else: a missing key is a
  `ConfigError` naming the key, never a quietly filled-in value. Adding a knob means
  editing `config.yaml` *and* the dataclass plus `_RULES` in `core/config.py`; one
  without the other is an error, not a default.
- Presentation constants are the exception and stay in their module: colours,
  thicknesses, fonts and label layout in `core/draw.py`, the KMeans `k` and the
  colour palette in `core/attributes.py`, the download size floors in
  `scripts/fetch_models.py`.
- **Never `cv2.imread` / `cv2.imwrite`.** Both go through a narrow-string path on
  Windows and fail silently on a Cyrillic path. Read with `np.fromfile` +
  `cv2.imdecode`, write with `cv2.imencode` + `Path.write_bytes`.
- **No NMS.** YOLO26 is NMS-free and removes its own duplicates; porting NMS from a
  YOLO11 example only costs accuracy.
- **No network outside `pip install` and `scripts/fetch_models.py`.** `Detector.__init__`
  checks the weights file on disk *before* `ultralytics` is imported, precisely so
  the Ultralytics auto-download can never fire.
- Imports behind a flag are lazy: `ultralytics` after the weights check,
  `sklearn` inside `_add_colors` under `--color`.
- Two override levels and no third: a CLI flag beats `config.yaml`, `config.yaml`
  beats nothing.
- Overrides go through `dataclasses.replace`; a loaded `Config` is never mutated.
- A usage error (bad path, bad config, missing weights) prints one sentence to
  stderr and returns `EXIT_USAGE` (2). No traceback.
- `Detection` gains no new fields for bookkeeping — a mark becomes a predicate
  (`is_debug`), because the field list is the cross-module contract.
- No abstraction around model choice: `n` → `s` is one line of `config.yaml`.
- A missing dependency is a blocker to report, not something to install.
- Do not edit `ARCHITECTURE.md`, `PROJECT_PROMPT.md`, `docs/` or `.autopilot/`.

## Tests

`venv\Scripts\python -m pytest -q` → 32 passed. `tests/conftest.py` puts the project
root on `sys.path`, so `import core` works without installing the package.

Three seams carry the suite, and no test ever loads a model or reaches the network:

1. `tests/test_geometry.py` — `offsets` against hand-computed values.
2. `tests/test_config.py` — a valid file loads; a wrong type or an out-of-range
   value fails with the key in the message; an unknown key only warns. The
   parametrized tail asserts the shipped `config.yaml` carries every documented key.
3. `tests/test_detector.py` — missing weights raise `FileNotFoundError` with the
   exact message, and a trap module replaces `ultralytics` to prove nothing in it
   is touched first.

`tests/test_detect_cli.py` covers the one piece of logic `detect.py` owns — the
drawn / near-miss split and the `--conf` interaction — with a `StubDetector`
returning a fixed list.

Drawing, JSON contents and the camera are accepted by eye, not automated.

## Pitfalls

- **`core/detector.py` must stay the only module that imports `ultralytics`.**
  It sets `YOLO_OFFLINE` and `YOLO_AUTOINSTALL=0` at module top level, before that
  import, and Ultralytics 8.4.157 reads `YOLO_OFFLINE` exactly once — while
  `ultralytics.utils` is imported (`ONLINE = is_online()`). A module that imports
  ultralytics earlier silently re-enables telemetry, and inference starts making
  outbound requests again. `scripts/fetch_models.py` sits outside that import path
  on purpose: it is the one place allowed to use the network.
  `tests/test_offline.py` guards this from a subprocess — in-process it would pass
  regardless, because Ultralytics mutes itself under pytest.
- **`ARCHITECTURE.md` §9 is out of date.** It predates `display.center_line`,
  `capture.camera/count/interval` and the whole `bench` section. `core/config.py`
  and `config.yaml` are the truth.
- `model.weights` is resolved against the **current working directory**, while
  `CONFIG_PATH` is resolved against `detect.py`. Run from the project root, or put
  an absolute path in `config.yaml`.
- `--conf` below `conf_debug` pulls `conf_debug` down with it. Without that the
  flag would silently show exactly what `0.25` already showed, and the JSON would
  hold no `"debug": true` entry at all.
- `core/events.py` keeps its registry in module state. Anything that registers
  handlers and hands control back calls `clear()` itself; nothing does it
  automatically.
- Renaming `configure_console`, `CONFIG_PATH` or `EXIT_USAGE` in `detect.py` breaks
  `bench.py` and `scripts/grab.py`, which import them.
- The console here is cp1252; `configure_console()` sets `errors="backslashreplace"`
  so a Cyrillic file name cannot kill a finished run. Importing `ultralytics`
  retunes stdout to UTF-8, so only the pre-model window is at risk.
- `torch.cuda.is_available()` is `False` by design — CPU-only wheels.
- `out\` is overwritten on every run. It is a debugging surface, not an archive.
- `cv2.imshow` on a machine with no display is not a failed run: `Window` says so
  once on stderr, disables itself and the files still get written.

## How Autopilot works here

Збірку веде навичка `/autopilot`. Вимоги, специфікація і таски — в `.autopilot/`.
Прогрес — `.autopilot/dashboard.html`. Правило: вимогу з `manifest.md`
може зняти тільки користувач.

Якщо робота триває — скажи «продовж автопілот»: стан підніметься
з `.autopilot/state.js`, перепитувати нічого не потрібно.
<!-- autopilot:end -->
