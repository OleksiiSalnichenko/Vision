<!-- autopilot:start -->
# Vision

Fully offline object detection on a CPU-only laptop. A photo, a folder, a video
file or a webcam goes in; for every detected object the app reports class,
confidence, bounding box, and how far the object's centre sits from the centre of
the frame — in pixels and as a fraction of half the frame. That offset is what a
pan-tilt camera gets steered with in a later phase. On video and webcam it also
tracks objects (ByteTrack ids), picks one target, and fires debounced rules from
`rules.yaml`. Built: phases 0, 0.5, 1 and 2. Next: phase 3 (`ui/`, PySide6).

Code, comments, log messages, README and UI strings are **English**.
Conversation with the user is Ukrainian.

## Commands

| Command | What it does |
|---|---|
| `py -3.11 -m venv venv` | create the project interpreter (Python 3.11) |
| `venv\Scripts\python -m pip install -r requirements.txt` | install dependencies |
| `venv\Scripts\python scripts\fetch_models.py` | one-time online step: weights + stock photo |
| `venv\Scripts\python scripts\export_openvino.py` | one-time offline export to `models\yolo26n_openvino_model\`; prints `skip:` when it exists, `--force` redoes it |
| `venv\Scripts\python detect.py --source data/test_images/bus.jpg` | detect on one image |
| `venv\Scripts\python detect.py --source data/test_images` | detect on a folder, file-name order |
| `venv\Scripts\python detect.py --source data/test_images/bus.jpg --no-window --conf 0.3 --classes person "cell phone" --color` | every flag at once |
| `venv\Scripts\python -c "import cv2,glob,numpy as n;w=cv2.VideoWriter('data/clip.mp4',cv2.VideoWriter_fourcc(*'mp4v'),10,(640,480));[w.write(cv2.resize(cv2.imdecode(n.fromfile(p,n.uint8),1),(640,480))) for p in sorted(glob.glob('data/test_images/*.jpg')) for _ in range(6)];w.release()"` | build a test clip `data\clip.mp4` from the test images |
| `venv\Scripts\python detect.py --source data/clip.mp4 --no-window` | video: rule events on the console, `out\clip.jsonl`, `out\clip_annotated.mp4` |
| `venv\Scripts\python detect.py --source camera:9 --no-window` | safe stream error path: `camera 9 is not available or busy`, exit 2 |
| `venv\Scripts\python detect.py --source camera:0` | live webcam, click a box to lock the target, `q`/`Esc`/Ctrl+C stops. **The user runs this, never an agent** |
| `venv\Scripts\python bench.py --source data/test_images/bus.jpg --runs 5` | seconds per frame and FPS (stills only) |
| `venv\Scripts\python bench.py --source data/test_images/bus.jpg --weights models/yolo26n.pt models/yolo26n_openvino_model` | `.pt` vs OpenVINO on the same frames, ends with `speedup vs first` |
| `venv\Scripts\python scripts\grab.py --camera 0 --count 5` | save webcam frames into `data\test_images\` (user only, opens the camera) |
| `venv\Scripts\python -m pytest -q` | tests (188 pass) |
| `venv\Scripts\python -m pytest -q tests\test_rules.py` | one test file |

Never plain `python`: the system interpreter is 3.7.3 and must stay untouched.
Switching the detector to OpenVINO is one line: `model.weights: models/yolo26n_openvino_model`.

## Structure

```
detect.py            the detection CLI and the only wiring
bench.py             timing harness, warm-up discarded; stills only
handlers.py          the user's functions for {call: name} rule actions (@on_detect)
config.yaml          every number, threshold and path in the project
rules.yaml           stream rules: debounce, zones, rules (still images ignore it)
requirements.txt     openvino pinned ==2026.3.1 (see Pitfalls)
core/                launch-agnostic modules: types, config, source, detector, tracker,
                     target, rules, geometry, draw, output, events, attributes, aim
scripts/             fetch_models.py (only networked code), export_openvino.py, grab.py
models/              *.pt, *_openvino_model/ — gitignored; checksums.txt tracked
data/test_images/    inputs — gitignored
out/                 <stem>.json, <stem>_annotated.jpg; streams: <stem>.jsonl,
                     <stem>_annotated.mp4 (video only), events/<stem>_<rule>_<index>.jpg
                     — gitignored, overwritten; camera stem is camera_N
tests/               one file per module + test_detect_cli, test_offline(_openvino), test_bench, test_export
docs/adr/            0001–0014 decision records (0007–0014 are phase 2) — read-only
ARCHITECTURE.md      design of record — stale in places, see Pitfalls
README.md            user-facing install / run / config / troubleshooting
```

## Key files

- `core/types.py` — `Detection(cls_id, cls_name, conf, bbox, center, dx, dy, dx_pct, dy_pct, color=None, track_id=None)`
  and `Frame(image, source, index, time=0.0)`. `track_id` is set only by the tracker
  on streams; `time` is seconds since the stream started (0 for stills). Fields are
  the cross-module contract; contract only, no logic.
- `core/config.py` — `load_config(path) -> Config`, `ConfigError(ValueError)`.
  `Config.model / .classes / .display / .output / .capture / .bench / .tracker / .rules`
  (`TrackerConfig(track_buffer, match_thresh, fuse_score)`, `RulesConfig(file)`). One
  rule per key in `_RULES` (type + range); a missing key raises naming the key, an
  unknown key only logs a warning.
- `core/source.py` — `Source(spec, cfg)`: `__iter__() -> Iterator[Frame]`, `__len__()`
  (0 for a camera = unknown), `is_stream`, `is_camera`, `fps` (0 for stills),
  `frame_size` (None for stills), `close()` (idempotent), context manager.
  `spec` is an image, a folder (name order, case-insensitive), a video file, or
  `camera:N` / a bare whole number that is not an existing path.
  `open_camera(index, cfg) -> cv2.VideoCapture` (DirectShow on Windows, buffer 1; raises
  `OSError("camera N is not available or busy")`), `is_stream_spec(spec)` (decides
  from the string, opens nothing), `IMAGE_EXTENSIONS`, `VIDEO_EXTENSIONS`,
  `CAMERA_PREFIX`, `CAMERA_BACKEND`. Errors: `ValueError("not a camera index: …")`,
  `ValueError("cannot open video: …")` in the constructor, `OSError("camera N stopped
  delivering frames")` mid-iteration, `RuntimeError("source already consumed: camera N")`
  on a second iteration of a camera. A camera is held from the constructor; a video
  is reopened per iteration (so it can be iterated twice). Video `time` = index / fps.
- `core/detector.py` — `Detector(cfg)`, `__call__(frame) -> list[Detection]` returning
  **everything from `conf_debug` upwards**, sorted by confidence descending.
  `is_debug(detection, cfg) -> bool` marks a near-miss. `require_weights(cfg)` (a file,
  or a folder holding `*.xml`). `MISSING_WEIGHTS_MESSAGE = "run scripts/fetch_models.py first"`,
  `MISSING_EXPORT_MESSAGE = "run scripts/export_openvino.py first"`,
  `OPENVINO_SUFFIX = "_openvino_model"`. `YOLO(path)` picks `.pt` or OpenVINO from the
  path; nothing else knows the format. Owns every offline switch (see Pitfalls).
- `core/tracker.py` — `Tracker(cfg)`, `update(frame, detections) -> list[Detection]`
  (same order, copies with `track_id` set or `None`, inputs untouched, an empty list
  still ages tracks), `reset()`. Wraps Ultralytics `BYTETracker` (Kalman + assignment,
  no weights). Boxes are never replaced by the tracker's smoothed ones. ByteTrack's
  high/new thresholds = `model.conf`, low = `model.conf_debug` — near-misses hold a
  track but never start one; only `tracker.*` keys are ByteTrack's own.
- `core/target.py` — `Targeting(cfg)`, `click(point, detections)` (locks the smallest
  tracked box under the point, empty space releases), `choose(detections, frame_size)
  -> TargetState(detection, locked, lost)` (frozen). Unlocked: tracked detection nearest
  the centre by `dx`/`dy`, tie → higher conf. Locked and absent: `lost=True` for up to
  `tracker.track_buffer` frames, then released. Only detections with a `track_id` count.
- `core/rules.py` — `load_rules(path) -> RuleSet`, `RulesError(ValueError)` naming
  `rules[<name>].<key>` / `debounce.<key>` / `zones.<name>`; missing file →
  `FileNotFoundError("rules file not found: …")`. `RuleSet(confirm_frames, cooldown,
  zones, rules)` + `calls() -> set[str]`; `Rule(name, when, cls, seconds, zone, actions)`
  (YAML `class` → `cls`); `RuleEngine(rule_set).update(time, detections) -> list[Event]`;
  `Event(rule, when, detection, time, actions)`; `actions` entries are `"log"`,
  `"save_frame"` or `("call", name)`. `CONDITIONS = appeared | disappeared | present |
  entered`, `SIMPLE_ACTIONS`, `CALL`. Pure: no print, no I/O, no handler calls.
  Debounce: `confirm_frames` consecutive frames to appear, disappear or change zone;
  cooldown keyed by (rule, track_id). `present` fires once per stay (after `seconds`
  from confirmation; a cooldown-suppressed one fires later); a suppressed
  `appeared`/`entered` is dropped. Zone membership uses the centre via `dx_pct`/`dy_pct`.
- `core/geometry.py` — `offsets(bbox, frame_size) -> (center, dx, dy, dx_pct, dy_pct)`.
  Pure. Right and down positive; centre and `dx`/`dy` rounded to whole pixels.
- `core/draw.py` — `annotate(image, detections, cfg, target=None, status=None) -> np.ndarray`,
  always a copy. Without `target`/`status` the output is byte-for-byte phase 1. On
  streams: `#id` in labels, magenta thick `TARGET` box, `status` line top-left. Takes
  the frame centre from `offsets((0,0,w,h),(w,h))` so crosshair and `dx`/`dy` zero agree.
- `core/output.py` — the only module in `core/` allowed to print. Stills:
  `write_json(source, detections, cfg, debug_detections=()) -> Path|None`,
  `write_image(source, image, cfg) -> Path|None`, `print_console(source, detections)`.
  JSON is `{"source", "detections": [{cls_id, cls_name, conf, bbox[4], center[2], dx, dy,
  dx_pct, dy_pct, color, debug}]}` — one array, near-misses carry `"debug": true`, no
  `track_id`. Streams: `StreamWriter(source, cfg, fps, frame_size, video)` (context
  manager; `write(frame, drawn, near_miss, target, canvas)`; `close() -> list[Path]`,
  idempotent; files open on first `write`; wrong canvas size → `ValueError`; fps 0 →
  25). JSONL line: `{source, index, time, target: {track_id, locked, lost}|null,
  detections: [{track_id, …photo fields…, debug}]}`, flushed per frame; a lost lock is
  `{"track_id": null, "locked": true, "lost": true}`. `.mp4` only for a video file with
  `output.save_image`, codec `mp4v`. `print_event(event)` →
  `[mm:ss.s] rule  cls #id conf  dx dy`, `write_event_frame(event, source, index, image,
  cfg) -> Path` (always written, ignores `save_image`),
  `print_stream_summary(frames, events, paths)` → `N frames, M events, wrote …`.
- `core/events.py` — `on_detect(cls=None)` decorator, `emit(detection)`, `call(name,
  detection)` (by function name, same class filter), `names()`, `subscriptions(name) ->
  set[str|None]`, `clear()`; `Handler = Callable[[Detection], None]`. A raising handler
  is logged and skipped.
- `core/attributes.py` — `dominant_color(image, bbox) -> str` over the palette
  red / orange / yellow / green / cyan / blue / purple / pink / brown / black /
  gray / white. `ValueError` on a degenerate box.
- `core/aim.py` — `aim(dx, dy) -> str`, an ASCII arrow; on streams called once per frame
  for the target only (status line). Stub seam for the servos.
- `detect.py` — `main(argv=None) -> int`, `parse_args`, `with_overrides(cfg, args)`,
  `process(frame, detector, cfg, want_color)` (one still), `run_images(...)`,
  `run_stream(source, detector, cfg, args, window, rule_set=None)`, `prepare_rules(cfg)
  -> RuleSet` (loads `rules.yaml` and, if any rule calls, `handlers.py` fresh via
  importlib; unknown name → `ValueError("unknown handler in rules.yaml: …")`; warns when a
  rule's class never reaches its handler), `Window(enabled, stream=False)` with
  `.show(image) -> bool`, `.on_click(cb)`, `.close()`; `configure_console()`,
  `CONFIG_PATH`, `HANDLERS_PATH`, `PROJECT_ROOT`, `EXIT_USAGE = 2`, `EXIT_STREAM_FAILED = 1`.
- `handlers.py` — user-editable; ships `on_phone` with `@on_detect(cls="cell phone")`
  for the `phone_at_door` rule. Imported only when a rule has `call`.
- `bench.py` — `one_pass`, `measure(detector, frames, runs, warmup)`, `report`,
  `report_speedup(results)`, `is_still(spec)`, `STILLS_ONLY_MESSAGE`; `--weights A [B …]`.
  Video and camera are refused by the path string before `Source` is built.
- `scripts/export_openvino.py` — `main(argv=None) -> int`, `--weights` (default
  `model.weights`, `.pt` only), `--force`; `target_for`, `is_complete`, `export`.
  FP32, static `model.imgsz` (changing `imgsz` means `--force`), `device="cpu"`.
  Prints `exported: …` / `skip: …`. A folder without `*.xml` is redone.
- `scripts/fetch_models.py` — no arguments, exit 0/1. Stages into `models\.part\`,
  verifies size floor + zip integrity, writes `models\checksums.txt`
  (`<sha256>  <path from project root>`), reports `downloaded` | `skip`.
- `scripts/grab.py` — `main(argv=None) -> int`, `grab`, `IMAGES_DIR`; uses
  `core.source.open_camera`.
- `tests/conftest.py` — `CONFIG_SCHEMA` (values deliberately differ from `config.yaml`),
  `schema_value(dotted)`, `config_text(overrides=None, without=())`, fixture
  `write_config`, `PROJECT_ROOT`.

## Architecture

`detect.py` is wiring and nothing else; every decision about *how* belongs to the
module it calls. `main`: `load_config(CONFIG_PATH)` → `with_overrides` → if
`is_stream_spec`: `prepare_rules` → `require_weights` → `Source(spec, cfg)` (a camera
switches on here) → `with source:` `Detector(cfg)` → `Window` → `run_images` or
`run_stream`. Everything that can fail as a usage error is checked before the camera
opens, and the `with` releases it on every exit, including a model that will not load.

One still (`run_images` → `process`, phase 1 unchanged): `Detector(frame)` → split with
`is_debug` into `drawn` / `near_miss` → optional `dominant_color` on `drawn` →
`draw.annotate` → `print_console` / `write_image` / `write_json(..., debug_detections=near_miss)`
→ `events.emit` per drawn detection → `Window.show` returns False on `q`/`Esc`.

One stream frame (`run_stream`; a new `Tracker`, `Targeting`, `RuleEngine` per stream):
`Detector(frame)` → `tracker.update` → `is_debug` split → optional colour →
`targeting.choose(drawn)` → status line (`aim` arrow, FPS over 30 frames) →
`draw.annotate(..., target, status)` → `engine.update(frame.time, drawn)` → per event,
in rule order: `log` → `print_event`, `save_frame` → `write_event_frame`, `call` →
`events.call` → `StreamWriter.write` → `Window.show` (non-blocking; left click →
`targeting.click` on the frame shown). Console prints events and one summary line,
nothing per frame. Exit 0 at end / `q` / Ctrl+C, 1 when the camera stops mid-run, 2 on a
file that cannot be written; files are closed and the summary printed on every path.

The load-bearing boundaries:

- **`detect.py` is the only caller of `is_debug`.** `draw.py`, `output.py`, `target.py`
  and `rules.py` are handed ready-made lists and know no confidence threshold.
  Moving the split into them would silently start drawing and printing near-misses.
  `tracker.py` reads `model.conf`/`conf_debug` only to set ByteTrack's bands.
- **`core/` never learns how it was launched.** No `argparse`, and no `print`
  outside `core/output.py`. `core/` must not import from a future `ui/`.
- **`core/rules.py` only computes.** Actions are carried out by `detect._act`.
- **Photos use `events.emit`; streams never do** — a handler runs on a stream only
  through a rule's `call` action. Rules never run on stills.
- **One inference pass, two thresholds.** The model runs at `conf_debug`; nothing
  below that floor ever reaches this process.
- **`Source` is the only input abstraction.** RTSP later changes that module and
  nothing downstream.
- `Targeting` releases a lock after `tracker.track_buffer` frames, matching ByteTrack
  only because `Tracker` passes no `frame_rate` (default 30 → buffer = `track_buffer`).
  Passing fps to `BYTETracker` requires changing `Targeting` too.
- `bench.py`, `scripts/grab.py` and `scripts/export_openvino.py` import
  `configure_console`, `CONFIG_PATH` and `EXIT_USAGE` from `detect.py`, so the
  console trap is closed in one place.

## Code conventions

- **No number is a constant in code if a user would ever turn it.** Those live in
  `config.yaml` (or `rules.yaml`), and there are no defaults anywhere else: a missing
  key is a `ConfigError` / `RulesError` naming the key, never a quietly filled-in
  value. Adding a knob means editing `config.yaml` *and* the dataclass plus `_RULES`
  in `core/config.py` (and `tests/conftest.CONFIG_SCHEMA`); one without the other is
  an error, not a default.
- Presentation constants are the exception and stay in their module: colours,
  thicknesses, fonts and label layout in `core/draw.py`, file suffixes, codec and
  fallback fps in `core/output.py`, the KMeans `k` and the palette in
  `core/attributes.py`, the download size floors in `scripts/fetch_models.py`.
- **Never `cv2.imread` / `cv2.imwrite`.** Both go through a narrow-string path on
  Windows and fail silently on a Cyrillic path. Read with `np.fromfile` +
  `cv2.imdecode`, write with `cv2.imencode` + `Path.write_bytes`. `cv2.VideoCapture`
  and `cv2.VideoWriter` have the same trap: `source._open_video` falls back to the
  8.3 short path, `StreamWriter` writes `.<ascii>.part.mp4` and renames on close.
- **No NMS.** YOLO26 is NMS-free and removes its own duplicates; the tracker adds none
  either.
- **No network outside `pip install` and `scripts/fetch_models.py`** — not on streams,
  not with the tracker, not with OpenVINO; the export is offline. `Detector.__init__`
  checks the weights on disk *before* `ultralytics` is imported, so the Ultralytics
  auto-download can never fire.
- Imports behind a flag are lazy: `ultralytics` inside `Detector`/`Tracker.__init__`
  and `export_openvino.export`, `sklearn` inside `_add_colors` under `--color`.
- Two override levels and no third: a CLI flag beats `config.yaml`, `config.yaml`
  beats nothing. Overrides go through `dataclasses.replace`; a loaded `Config` is
  never mutated.
- A usage error (bad path, bad config or rules, unknown handler, missing weights or
  export, busy camera, unwritable output) prints one sentence to stderr and returns
  `EXIT_USAGE` (2). No traceback.
- `Detection` gains no new fields for bookkeeping — a mark becomes a predicate
  (`is_debug`). `track_id` and `Frame.time` were added by decision (docs/adr/0007).
- No abstraction around model choice: `n` → `s`, or `.pt` → OpenVINO, is one line of
  `config.yaml`. The default stays `.pt` (docs/adr/0011).
- Tests take tunable values from `conftest.schema_value` / `config_text`, never copy
  numbers from `config.yaml`.
- A missing dependency is a blocker to report, not something to install.
- Edit UTF-8 files with the Write/Edit tools: PowerShell 5.1 `Get-Content`/`Set-Content`
  re-encode through the ANSI code page and corrupt them.
- Do not edit `ARCHITECTURE.md`, `PROJECT_PROMPT.md`, `docs/` or `.autopilot/`.

## Tests

`venv\Scripts\python -m pytest -q` → 188 passed. `tests/conftest.py` puts the project
root on `sys.path`, so `import core` works without installing the package.

No test loads a model, reaches the network, or opens a real camera. The seams:

1. `test_geometry` — `offsets` against hand-computed values.
2. `test_config` — valid file loads; wrong type / out of range fails naming the key;
   unknown key warns; the shipped `config.yaml` carries every schema key.
3. `test_detector` — missing weights/export raise with the exact message; a trap module
   replaces `ultralytics` to prove nothing in it is touched first.
4. `test_offline` (3 subprocess scenarios, incl. `core.tracker` update) and
   `test_offline_openvino` (2) — sockets trapped in a child process; must stay
   subprocesses, since in-process Ultralytics mutes itself under pytest.
5. `test_tracker`, `test_target`, `test_rules` — synthetic `Detection`s with ids and time.
6. `test_source` — a tiny video written into `tmp_path` (also under a Cyrillic name);
   the camera is a monkeypatched `open_camera`.
7. `test_output`, `test_draw` — JSONL/mp4/event files, phase-1 JSON shape, photo overlay
   byte-for-byte phase 1.
8. `test_detect_cli` — `StubDetector` + fake sources: the drawn / near-miss split,
   `--conf`, `run_stream` output, handler loading, camera release on every exit path,
   rules/weights errors never switching the camera on.
9. `test_bench` (trap for `Source`/`open_camera`: `camera:0` and `0` must be refused
   first), `test_export`, `test_events`, `test_types`.

Accepted by eye, not automated: the look of the overlay, a real webcam run, click-to-lock.

## Pitfalls

- **Offline import order.** `core/detector.py` sets, at module top level before any
  ultralytics/torch/openvino import: `YOLO_OFFLINE=1`, `YOLO_AUTOINSTALL=0`,
  `KMP_BLOCKTIME=0`, and `sys.modules["openvino_telemetry"] = None` (assigned, not
  `setdefault`). Ultralytics 8.4.157 reads `YOLO_OFFLINE` exactly once, while
  `ultralytics.utils` is imported; `import openvino` posts a Google Analytics event
  unless its telemetry package fails to import. So only `core/detector.py`,
  `core/tracker.py` and `scripts/export_openvino.py` import `ultralytics`, the latter
  two with `import core.detector` as their first project import, and `ultralytics`
  itself lazily inside a function. Nothing imports `openvino` directly.
  `scripts/fetch_models.py` stays outside this path on purpose: it is the network step.
- **`KMP_BLOCKTIME=0` is a speed switch.** Without it torch's OpenMP threads spin on all
  4 cores between frames and OpenVINO drops to ~0.18 s/frame, slower than `.pt`.
- **`openvino==2026.3.1` is pinned.** 2026.4.0 exposes this laptop's Intel iGPU,
  Ultralytics' AUTO device compiles for it and the process dies with 0xC0000005.
  Do not upgrade it.
- **OpenVINO gain is measured 1.54x** (bus.jpg, 3 warm-up + 10 runs: `.pt` 0.079 s,
  OpenVINO 0.051 s), not the "2-3x" / ~39 ms in ARCHITECTURE.md §2/§4. Single runs on
  this 4-core U-CPU swing ±30% or more; re-measure with `bench.py --weights`, don't quote.
  The OpenVINO folder compiles twice at start-up ("Loading …" printed twice).
- **A new object has `track_id=None` on its first frame** (except on a stream's first
  frame): ByteTrack confirms on the second sighting. Overlay, JSONL, targeting and
  rules must live with `None`; only tracked detections can be a target or fire a rule.
- **One `Tracker` / `Targeting` / `RuleEngine` per stream.** ByteTrack's `STrack` id
  counter is process-wide, and a new `Tracker` or `reset()` restarts numbering for
  everyone; rule cooldowns are keyed by (rule, track_id) and never cleared.
- **No test and no agent opens a real camera** (`camera:0`, bare `0`, `grab.py`) — it
  once held the user's webcam. A bare whole number that is not an existing path *is*
  a camera; `bench.py` refuses by string before `Source`. Use `camera:9` for the error path.
- **`ARCHITECTURE.md` is stale** in §2/§4 (OpenVINO numbers), §6 (phase 2 "Rewritten:
  nothing" — every existing `core/` module but geometry/attributes/aim changed, and
  every entry point), §7 (`Detection`/`Frame` lack `track_id`/`time`; no tracker,
  target, rules contracts) and §9 (predates `display.center_line`,
  `capture.camera/count/interval`, `bench`, `tracker`, `rules`). The code,
  `config.yaml` and `docs/adr/` are the truth.
- FFmpeg prints its own stderr line (e.g. `moov atom not found`) on a broken `.mp4`
  before our one-sentence error; it cannot be silenced from the process.
- `model.weights` is resolved against the **current working directory**, while
  `CONFIG_PATH`, `rules.file` and `HANDLERS_PATH` are resolved against `detect.py`.
  Run from the project root, or put an absolute path in `config.yaml`.
- `--conf` below `conf_debug` pulls `conf_debug` down with it. Without that the
  flag would silently show exactly what `0.25` already showed, and the JSON would
  hold no `"debug": true` entry at all.
- `core/events.py` keeps its registry in module state. Anything that registers
  handlers and hands control back calls `clear()` itself; `main` and `run_stream`
  do it after a stream whose rules call handlers.
- `handlers.py` runs on the detection loop: a slow handler slows the video by the
  same amount.
- Renaming `configure_console`, `CONFIG_PATH` or `EXIT_USAGE` in `detect.py` breaks
  `bench.py`, `scripts/grab.py` and `scripts/export_openvino.py`.
- The console here is cp1252; `configure_console()` sets `errors="backslashreplace"`
  so a Cyrillic file name cannot kill a finished run. Importing `ultralytics`
  retunes stdout to UTF-8, so only the pre-model window is at risk.
- A camera delivering a size other than `capture.width/height` only logs a warning;
  `StreamWriter` uses the actual `Source.frame_size`.
- `.mp4` output fails with `OSError` when `output.dir` itself is outside the code page.
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
