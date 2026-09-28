<!-- autopilot:start -->
# Vision

Fully offline object detection on a CPU-only laptop. A photo, a folder, a video
file or a webcam goes in; for every detected object the app reports class,
confidence, bounding box, and how far the object's centre sits from the centre of
the frame — in pixels and as a fraction of half the frame. That offset is what a
pan-tilt camera gets steered with in a later phase. On video and webcam it also
tracks objects (ByteTrack ids), picks one target, and fires debounced rules from
`rules.yaml`. Two front ends run the same frame order (`core/pipeline.py`): the CLI
`detect.py` and the PySide6 desktop app `app.py` (live view, threshold slider, object
list, events, settings panel with Save to `config.yaml`). Built: phases 0, 0.5, 1, 2
and 3. Next: phase 4 (custom classes, `training/`).

Code, comments, log messages, README and UI strings are **English**.
Conversation with the user is Ukrainian.

## Commands

| Command | What it does |
|---|---|
| `py -3.11 -m venv venv` | create the project interpreter (Python 3.11) |
| `venv\Scripts\python -m pip install -r requirements.txt` | install dependencies |
| `venv\Scripts\python scripts\fetch_models.py` | one-time online step: weights + stock photo |
| `venv\Scripts\python scripts\export_openvino.py` | one-time offline export to `models\yolo26n_openvino_model\` — the default model, so required after `fetch_models.py` before the first run; prints `skip:` when it exists, `--force` redoes it (needed after an `imgsz` change) |
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
| `venv\Scripts\python app.py --help` | desktop app flags; imports no Qt, opens nothing — the only `app.py` call an agent makes |
| `venv\Scripts\python app.py --source data/test_images` | desktop app, folder opened once the model is in; Prev/Next, slider, Save. **User only: opens a window** |
| `venv\Scripts\python app.py` | desktop app, pick a file / folder / camera in the window. **User only** |
| `venv\Scripts\python -m pytest -q` | tests (324 pass) |
| `venv\Scripts\python -m pytest -q tests\test_rules.py` | one test file |
| `venv\Scripts\python -m pytest -q tests\test_ui_window.py` | one Qt test file (offscreen, no window, stub model and camera) |

Never plain `python`: the system interpreter is 3.7.3 and must stay untouched.
The default model is OpenVINO (`model.weights: models/yolo26n_openvino_model`, docs/adr/0021);
switching back to PyTorch is one line: `model.weights: models/yolo26n.pt`.

## Structure

```
detect.py            the detection CLI: flags, console, exit codes over core/pipeline.py
app.py               the desktop app entry point: loads config.yaml, builds MainWindow
bench.py             timing harness, warm-up discarded; stills only
handlers.py          the user's functions for {call: name} rule actions (@on_detect)
config.yaml          every number, threshold and path in the project
rules.yaml           stream rules: debounce, zones, rules (still images ignore it)
requirements.txt     openvino pinned ==2026.3.1 (see Pitfalls); PySide6, pytest-qt
core/                launch-agnostic modules: types, config, source, detector, tracker,
                     target, rules, geometry, draw, output, events, attributes, aim,
                     pipeline (the frame order both front ends run)
ui/                  PySide6 only: worker.py (QThread worker), main_window.py, view.py,
                     settings_panel.py
scripts/             fetch_models.py (only networked code), export_openvino.py, grab.py
models/              *.pt, *_openvino_model/ — gitignored; checksums.txt tracked
data/test_images/    inputs — gitignored
out/                 <stem>.json, <stem>_annotated.jpg; streams: <stem>.jsonl,
                     <stem>_annotated.mp4 (video only), events/<stem>_<rule>_<index>.jpg
                     — gitignored, overwritten; camera stem is camera_N
tests/               one file per module + test_detect_cli, test_pipeline, test_offline(_openvino,_ui),
                     test_bench, test_export, test_ui_{worker,window,settings,view,boundaries}
docs/adr/            0001–0021 decision records (0007–0014 phase 2, 0015–0020 phase 3,
                     0021 OpenVINO default, supersedes 0011) — read-only
ARCHITECTURE.md      design of record — the user's document; see Pitfalls
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
  unknown key only logs a warning; unparseable YAML → `ConfigError("config file is not
  valid YAML: …")`. `DisplayConfig.color` (`display.color`) turns on
  what `--color` does, without the flag. `save_values(path, values: dict[str, Any])` — dotted
  keys or `"classes"`; rewrites only the value after `key:` line by line (indent,
  trailing comment, commented-out lines, CRLF kept; `classes` rewritten as a block),
  floats rounded to 6 digits, writes `.<name>.tmp`, `load_config`s it, then `os.replace`.
  `ConfigError` naming the key for: unknown key, key absent from the file, value
  `_RULES` refuses, `classes` not `list[str]`, a `classes` list with blank/comment lines
  between items. `_checked_classes` is the one classes rule for load and save.
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
  `names -> dict[int, str]` (property, a copy); `set_classes(classes)` swaps the whitelist
  without a reload (`[]` = all; unknown name → `ValueError("unknown class names in
  config: …")`, filter unchanged).
- `core/tracker.py` — `Tracker(cfg)`, `update(frame, detections) -> list[Detection]`
  (same order, copies with `track_id` set or `None`, inputs untouched, an empty list
  still ages tracks), `reset()`. Wraps Ultralytics `BYTETracker` (Kalman + assignment,
  no weights). Boxes are never replaced by the tracker's smoothed ones. ByteTrack's
  high/new thresholds = `model.conf`, low = `model.conf_debug` — near-misses hold a
  track but never start one; only `tracker.*` keys are ByteTrack's own.
  `set_conf(conf)` moves the high/new bands mid-stream; tracks, ids and the low band stay.
- `core/target.py` — `Targeting(cfg)`, `click(point, detections)` (locks the smallest
  tracked box under the point, empty space releases), `choose(detections, frame_size,
  new_frame=True) -> TargetState(detection, locked, lost)` (frozen). Unlocked: tracked
  detection nearest the centre by `dx`/`dy`, tie → higher conf. Locked and absent:
  `lost=True` for up to `tracker.track_buffer` frames, then released; `new_frame=False`
  (a paused frame redrawn) never advances that count. Only detections with a `track_id` count.
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
  always a copy. All text sits on filled dark plates (`_put_text`; a thick black
  outline read as a smeared copy and was replaced 2026-09-28). Without
  `target`/`status` the photo overlay is pinned by a checksum in `test_draw`. On
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
  `output.save_image`, codec `mp4v`. `format_event(event) -> str` →
  `[mm:ss.s] rule  cls #id conf  dx dy`, `format_summary(frames, events, paths) -> str` →
  `N frames, M events, wrote …`; `print_event` / `print_stream_summary` print exactly
  those, the app's event list and status bar show them. `write_event_frame(event,
  source, index, image, cfg) -> Path` (always written, ignores `save_image`).
- `core/pipeline.py` — the frame order, shared by `detect.py` and `ui/worker.py`; no print.
  `prepare_rules(rules_path, handlers_path) -> RuleSet` (rules, then `handlers.py` fresh
  via importlib when a rule calls; unknown name → `ValueError("unknown handler in
  rules.yaml: …")`; warns when a rule's class never reaches its handler; bus cleared on
  failure). Stills: `StillResult(canvas, drawn, near_miss, detections)` (frozen;
  `detections` = all from `conf_debug`), `process_still(frame, detector, cfg, want_color)`
  (writes nothing, **never `events.emit`** — the caller emits), `resplit_still(frame,
  detections, cfg, want_color)` (no model, input untouched, colour in copies; nobody emits
  after it), `save_still(source, result, cfg, on_written=None) -> list[Path]` (image, then
  JSON; callback after each). Streams: `StreamSession(detector, cfg, rule_set, fps,
  frame_size|None, is_video, on_log: Callable[[Event], None], want_color)` — context
  manager owning `Tracker`, `Targeting`, `RuleEngine`, `StreamWriter`, FPS window (30);
  `step(frame) -> StreamResult(canvas, drawn, near_miss, target, events, status)`;
  `redraw()` (last frame under current cfg/lock, no detector, no rules, no writes,
  `events == ()`; `RuntimeError` before the first `step`); `click(point)`; `retune(cfg,
  want_color)` (next frame on; `Tracker.set_conf`; open files keep their cfg);
  `set_detector(d)`; `close() -> list[Path]` idempotent; `frames`, `fired`, `fps`.
  Actions: `log` → `on_log`, `save_frame` / `call` carried out here.
  `StreamWriteError(OSError)` is the only `OSError` `step` raises for its own writes
  (event frame, JSONL, mp4); an `OSError` from detector/tracker/draw/handler passes
  through as is. `core.output`/`core.events` are reached via the module attribute, so
  monkeypatching them in tests reaches the pipeline.
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
  `process(frame, detector, cfg, want_color) -> canvas` (one still: `process_still` →
  `print_console` → `save_still` printing `  wrote …` per file → `events.emit`),
  `run_images(...)`, `run_stream(source, detector, cfg, args, window, rule_set=None)`
  (a `StreamSession`; catches only `StreamWriteError` → exit 2), `prepare_rules(cfg) ->
  RuleSet` (wraps `pipeline.prepare_rules(PROJECT_ROOT / cfg.rules.file, HANDLERS_PATH)`,
  reading `HANDLERS_PATH` at call time), `want_color(args, cfg)` = `args.color or
  cfg.display.color`,
  `Window(enabled, stream=False)` with `.show(image) -> bool`, `.on_click(cb)`, `.close()`;
  `configure_console()`, `CONFIG_PATH`, `HANDLERS_PATH`, `PROJECT_ROOT`,
  `EXIT_USAGE = 2`, `EXIT_STREAM_FAILED = 1`. No module attribute `draw` any more.
- `app.py` — `main(argv=None) -> int`, `parse_args` (`--source` only), `make_worker(cfg)
  -> PipelineWorker(cfg, Detector, Source)`. Bad/missing `config.yaml` → one sentence,
  `EXIT_USAGE`, no Qt imported; everything later (weights, camera, rules) is a message
  box and the app stays open. `--source` is queued behind `load_model`.
- `ui/worker.py` — `FramePayload(canvas, drawn, near_miss_count, target_track_id, index,
  total, fps, source, is_stream)` (frozen; canvas and detections are copies; `total` 0 =
  camera). `PipelineWorker(cfg, detector_factory, source_factory, parent=None)` (QObject,
  owns model, source, still cache, `StreamSession`). Slots: `load_model()`,
  `open_source(spec)` (stops the old one; rules → weights → source, like `detect.main`),
  `stop()`, `shutdown()` (stop + `thread().quit()`), `set_paused(bool)` (video only),
  `click(x, y)`, `set_conf(float)`, `commit_still()` (rewrite the photo's files after the
  slider), `show_index(i)` (model once per photo, then `resplit_still` from cache),
  `apply(cfg)` (weights/imgsz changed → rebuild detector, stream keeps tracks; classes →
  `set_classes`; else redraw; keeps `model.conf/conf_debug` — threshold only via
  `set_conf`), `frame_shown()`. Signals: `model_ready(dict)`, `model_failed(str)`,
  `frame_ready(FramePayload)`, `event(str)`, `failed(str)`, `finished(summary)`,
  `applied(Config)` — the config really in force (old values after a failed model or
  unknown class).
- `ui/main_window.py` — `MainWindow(cfg, worker_factory)`: owns a `QThread`, moves the
  worker onto it, commands via queued signals; `open_source(spec)`, `toggle_pause()`
  (Space). `_OpenRelay` on the worker thread emits `opening(n)` so frames of a previous
  open are dropped. Slider range `conf_debug..1` in hundredths. `unsaved_values(session,
  on_disk, models_dir) -> dict` (only `model.weights`, `model.imgsz`, `model.conf`,
  `classes`, `display.center_line`, `display.color`), `saved_text(keys)`,
  `near_miss_text(n)`, `file_filter()`, `MODELS_DIR = PROJECT_ROOT / "models"`,
  `WINDOW_TITLE`, `*_TEXT`, `COLUMNS`, `TARGET_MARK`. Public widgets are attributes
  (`view`, `slider`, `table`, `settings`, `status_label`, `notice_label`, buttons …).
- `ui/view.py` — `fit_rect`, `to_image_point(widget_point, widget_size, image_size)` (None
  in a bar), `to_qimage(bgr)`; `FrameView(placeholder)` with `show_image`, `clear`,
  signal `clicked(x, y)` in frame pixels.
- `ui/settings_panel.py` — `SettingsPanel(cfg, models_dir)`: `set_class_names(names)`,
  `set_config(cfg)` (no signal), `config()`; signals `changed(Config)`, `save_requested()`.
  `model_choices(models_dir, current)`, `model_entry(models_dir, weights)` (the one
  spelling `models/<entry>`), `is_openvino(weights)`. OpenVINO choice disables `imgsz`
  and puts it back to the start value. Whitelisted names the model lacks stay listed.
- `handlers.py` — user-editable; ships `on_phone` with `@on_detect(cls="cell phone")`
  for the `phone_at_door` rule. Imported only when a rule has `call`.
- `bench.py` — `one_pass`, `measure(detector, frames, runs, warmup)`, `report`,
  `report_speedup(results)`, `is_still(spec)`, `STILLS_ONLY_MESSAGE`; `--weights A [B …]`.
  Video and camera are refused by the path string before `Source` is built.
- `scripts/export_openvino.py` — `main(argv=None) -> int`, `--weights` (default
  `model.weights`; an `*_openvino_model` folder maps to the `.pt` beside it via
  `source_for`, since the folder is the shipped default), `--force`; `source_for`,
  `target_for`, `is_complete`, `export`.
  FP32, static `model.imgsz` (changing `imgsz` means `--force`), `device="cpu"`.
  Prints `exported: …` / `skip: …`. A folder without `*.xml` is redone.
- `scripts/fetch_models.py` — no arguments, exit 0/1. Stages into `models\.part\`,
  verifies size floor + zip integrity, writes `models\checksums.txt`
  (`<sha256>  <path from project root>`), reports `downloaded` | `skip`.
- `scripts/grab.py` — `main(argv=None) -> int`, `grab`, `IMAGES_DIR`; uses
  `core.source.open_camera`.
- `tests/conftest.py` — `CONFIG_SCHEMA` (values deliberately differ from `config.yaml`),
  `schema_value(dotted)`, `config_text(overrides=None, without=())`, fixture
  `write_config`, `PROJECT_ROOT`. Schema has `display.color = True`.

## Architecture

`core/pipeline.py` owns the order of a frame; `detect.py` and `ui/worker.py` only
decide *when* a frame runs and where its output goes. `detect.main`:
`load_config(CONFIG_PATH)` → `with_overrides` → if `is_stream_spec`: `prepare_rules` →
`require_weights` → `Source(spec, cfg)` (a camera switches on here) → `with source:`
`Detector(cfg)` → `Window` → `run_images` or `run_stream`. Everything that can fail as a
usage error is checked before the camera opens, and the `with` releases it on every
exit, including a model that will not load. `PipelineWorker.open_source` checks in the
same order (rules → weights → source) and reports by `failed(str)`.

One still (`process_still`): `Detector(frame)` → split with `is_debug` into `drawn` /
`near_miss` → optional `dominant_color` on `drawn` → `draw.annotate`; then the caller:
CLI `print_console` → `save_still` (`write_image`, `write_json(..., debug_detections=
near_miss)`) → `events.emit` per drawn → `Window.show` (False on `q`/`Esc`); app: payload
→ `save_still` → `events.emit`, once per photo. Slider on a photo: `resplit_still` from the
cached detections, files rewritten by `commit_still` when the slider is released.

One stream frame (`StreamSession.step`; one session per stream): `Detector(frame)` →
`tracker.update` → `is_debug` split → optional colour → `targeting.choose(drawn)` →
status line (`aim` arrow, FPS over 30 frames) → `draw.annotate(..., target, status)` →
`engine.update(frame.time, drawn)` → per event, in rule order: `log` → `on_log` (CLI
`print_event`, app `event` signal with `format_event`), `save_frame` →
`write_event_frame`, `call` → `events.call` → `StreamWriter.write`. CLI: `Window.show`
(non-blocking; left click → `session.click`); console prints events and one summary
line, nothing per frame. Exit 0 at end / `q` / Ctrl+C, 1 when the camera stops mid-run,
2 on a file that cannot be written; files are closed and the summary printed on every path.

The app: `app.main` → `load_config` → `QApplication` → `MainWindow(cfg, make_worker)` →
worker moved to the window's `QThread` → `load_model` queued → `--source` queued after.
A stream is one `QTimer.singleShot(0)` tick per frame on the worker thread, so stop /
pause / click / threshold / apply run between frames with no locks; a generation number
makes ticks of a stopped stream no-ops. Settings panel change → `changed(Config)` →
`worker.apply` → `applied(Config)` → `settings.set_config` (the panel shows what is really
in force). Save → `unsaved_values(session, load_config(CONFIG_PATH), MODELS_DIR)` →
`save_values` → `notice_label`. Close → `shutdown` queued → `QThread.wait()` (no
timeout) → camera released before the window is gone.

The load-bearing boundaries:

- **`core/pipeline.py` is the only caller of `is_debug`** (defined in `core/detector.py`).
  `draw.py`, `output.py`, `target.py`, `rules.py`, `detect.py` and `ui/` are handed
  ready-made lists and know no confidence threshold. Moving the split into them would
  silently start drawing and printing near-misses. `tracker.py` reads
  `model.conf`/`conf_debug` only to set ByteTrack's bands.
- **`core/` never learns how it was launched.** No `argparse`, no `print` outside
  `core/output.py`, and no import of `PySide6`, `shiboken6` or `ui` — enforced by
  `test_ui_boundaries` on the source text. `ui/` imports `core/` and `detect`.
- **The UI thread never touches the model, source or session.** Commands go as queued
  signals, frames come back as `FramePayload` copies. Back-pressure: the window calls
  `frame_shown()` once for every `frame_ready` it takes (painted, replaced or dropped);
  until then the worker still processes, writes and runs rules on every frame but holds
  only the newest payload. A stream's last frame is always flushed at its natural end;
  stop/open drop the held one. The window paints via a queued signal, not a zero timer
  (posted events starve timers).
- **The threshold goes only through `set_conf`.** `apply` keeps the session's
  `model.conf`/`conf_debug`; `conf_debug` is fixed for the session (slider floor).
- **The worker catches `StreamWriteError` around `step`, never bare `OSError`**; any
  other frame error is `failed` + end of stream, and the app stays alive.
- **`core/rules.py` only computes.** Actions are carried out by `StreamSession._act`.
- **Photos use `events.emit`; streams never do** — a handler runs on a stream only
  through a rule's `call` action. Rules never run on stills.
- **One inference pass, two thresholds.** The model runs at `conf_debug`; nothing
  below that floor ever reaches this process.
- **`Source` is the only input abstraction.** RTSP later changes that module and
  nothing downstream.
- `Targeting` releases a lock after `tracker.track_buffer` frames, matching ByteTrack
  only because `Tracker` passes no `frame_rate` (default 30 → buffer = `track_buffer`).
  Passing fps to `BYTETracker` requires changing `Targeting` too.
- `bench.py`, `scripts/grab.py`, `scripts/export_openvino.py` and `app.py` import
  `configure_console`, `CONFIG_PATH` and `EXIT_USAGE` from `detect.py`, so the
  console trap is closed in one place; `ui/main_window.py` also takes
  `PROJECT_ROOT`, `ui/worker.py` `detect.prepare_rules`.
- `config.yaml` is written only by `save_values`, line by line — never by dumping YAML,
  which would drop the user's comments and commented-out lines.

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
  and `export_openvino.export`, `sklearn` inside `pipeline._add_colors` only with colour
  on, `PySide6`/`ui` inside `app.main`/`app.make_worker` after the config loaded.
- Two override levels and no third: a CLI flag beats `config.yaml`, `config.yaml`
  beats nothing; in the app the panel/slider change the session only, until Save.
  Overrides go through `dataclasses.replace`; a loaded `Config` is never mutated.
- A usage error (bad path, bad config or rules, unknown handler, missing weights or
  export, busy camera, unwritable output) prints one sentence to stderr and returns
  `EXIT_USAGE` (2). No traceback. In the app the same sentence goes to
  `QMessageBox.warning` via `failed`/`model_failed`, and the app stays open.
- Qt-facing values that are presentation only (slider scale 100, window size, camera
  spin max 99, notice 5 s, `imgsz` step 32) stay as module constants in `ui/`.
- UI strings, logs and comments in `ui/` and `app.py` carry no Cyrillic
  (`test_ui_boundaries` greps for it).
- `Detection` gains no new fields for bookkeeping — a mark becomes a predicate
  (`is_debug`). `track_id` and `Frame.time` were added by decision (docs/adr/0007).
- No abstraction around model choice: `n` → `s`, or `.pt` → OpenVINO, is one line of
  `config.yaml`. The default is OpenVINO (docs/adr/0021, superseding 0011); `.pt` is
  one line away.
- Tests take tunable values from `conftest.schema_value` / `config_text`, never copy
  numbers from `config.yaml`.
- A missing dependency is a blocker to report, not something to install.
- Edit UTF-8 files with the Write/Edit tools: PowerShell 5.1 `Get-Content`/`Set-Content`
  re-encode through the ANSI code page and corrupt them.
- Do not edit `ARCHITECTURE.md`, `PROJECT_PROMPT.md`, `docs/` or `.autopilot/`.

## Tests

`venv\Scripts\python -m pytest -q` → 324 passed. `tests/conftest.py` puts the project
root on `sys.path`, so `import core` works without installing the package.

No test reaches the network or opens a real camera or an on-screen window; only the
subprocess offline tests load the real model. The seams:

1. `test_geometry` — `offsets` against hand-computed values.
2. `test_config` — valid file loads; wrong type / out of range fails naming the key;
   unknown key warns; the shipped `config.yaml` carries every schema key; `save_values`
   keeps comments/indent/CRLF and leaves the file untouched on every refusal.
3. `test_detector` — missing weights/export raise with the exact message; a trap module
   replaces `ultralytics` to prove nothing in it is touched first.
4. `test_offline` (3 subprocess scenarios, incl. `core.tracker` update) and
   `test_offline_openvino` (2) — sockets trapped in a child process; must stay
   subprocesses, since in-process Ultralytics mutes itself under pytest.
   `test_offline_ui` (1) — the same trap around `MainWindow` + `app.make_worker` on the
   model `config.yaml` names and `data/test_images/bus.jpg`, output in `tmp_path`; skips
   when that model or photo is missing.
5. `test_tracker`, `test_target`, `test_rules` — synthetic `Detection`s with ids and time.
6. `test_source` — a tiny video written into `tmp_path` (also under a Cyrillic name);
   the camera is a monkeypatched `open_camera`.
7. `test_output`, `test_draw` — JSONL/mp4/event files, phase-1 JSON shape, photo overlay
   pinned by checksum (change it only after looking at a rendered image).
8. `test_detect_cli` — `StubDetector` + fake sources: the drawn / near-miss split,
   `--conf`, `run_stream` output, handler loading, camera release on every exit path,
   rules/weights errors never switching the camera on.
9. `test_pipeline` — `StubDetector` + synthetic frames, real ByteTrack: split, resplit,
   `save_still`, `StreamSession` step/redraw/retune/click, `StreamWriteError` vs other `OSError`.
10. `test_ui_worker` — `PipelineWorker` on stub `detector_factory`/`source_factory` (the
    "camera" is a generator), `qtbot.waitSignal`; mostly on the test thread, some on a
    joined `QThread`. `test_ui_window` — `MainWindow` driving a real worker on stubs,
    `app.main`; `QMessageBox` replaced by a fake that records warnings; `MODELS_DIR` /
    `CONFIG_PATH` monkeypatched. `test_ui_settings` — the panel and `model_choices`.
    `test_ui_view` — `to_image_point` arithmetic. `test_ui_boundaries` — AST import
    scan of `core/` and a Cyrillic grep of `ui/` + `app.py`, no Qt started.
11. `test_bench` (trap for `Source`/`open_camera`: `camera:0` and `0` must be refused
    first), `test_export`, `test_events`, `test_types`.

Accepted by eye, not automated: the look of the overlay and of the window, a real
webcam run (CLI and app), click-to-lock.

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
- **No test and no agent opens a real camera** (`camera:0`, bare `0`, `grab.py`, the app) — it
  once held the user's webcam. A bare whole number that is not an existing path *is*
  a camera; `bench.py` refuses by string before `Source`. Use `camera:9` for the error path.
- **`ARCHITECTURE.md`** was brought up to date with phases 1–3 on 2026-09-28 (§2–§4
  measured numbers and OpenVINO default, §6 phase table, §7 `track_id`/`time`, §9
  schema, §10). Still stale: the «Status» line at the top and the §6 file tree
  (phase 1 only). It is the user's document — edit only with their yes. Where it
  disagrees, the code, `config.yaml` and `docs/adr/` are the truth.
- **No agent launches `app.py` except `--help`.** Any other run opens a window on the
  user's screen, and its Open camera / `--source camera:N` holds the webcam until the
  window closes. Drive the app only through `test_ui_*` (offscreen, stubs).
- **Qt tests are offscreen only.** Every Qt test module sets
  `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before its first Qt import; a
  new one must too (and `setdefault` means an outer `QT_QPA_PLATFORM` wins — do not set
  one). Any code path reaching `QMessageBox`/`QFileDialog` must be monkeypatched in
  tests, or the modal blocks the run.
- **ByteTrack's first import costs ~3 s.** `Tracker.__init__` imports it lazily; under a
  loaded CPU that eats most of `TIMEOUT_MS = 5000` in the first stream test.
  `test_ui_window` pays it in a module-scoped autouse fixture (`import core.detector`
  first). A new Qt test file that starts streams needs the same.
- **Forgetting `frame_shown()` freezes the display, not the pipeline.** A new consumer of
  `frame_ready` must acknowledge every payload it takes, including ones it drops.
- **`config.yaml` is read once at app start.** Hand edits made while the app runs are not
  seen; Save compares the session to the file *as it is on disk now* and writes only the
  six keys that differ (so other hand edits survive, but a hand edit to one of those six
  is overwritten by the session value). Save of a `classes` list with blank or comment
  lines between items is refused.
- `config.yaml` currently carries an uncommitted user edit (`model.weights` → the
  OpenVINO folder, the `.pt` line commented out). Do not revert or commit it;
  `test_offline_ui` runs on whatever model it names.
- A `.pt` → OpenVINO switch in the panel pins `imgsz` to the value the panel started with
  (the export is static); `imgsz` or weights changes reload the detector on the worker
  thread, and a failed load keeps the old model running (`applied` reverts the panel).
- `closeEvent` waits for the worker thread with no timeout: a frame stuck in a slow
  handler or model call keeps the process alive until it returns (the window hides
  first, so it does not look frozen).
- A `failed` before the first frame of the newest open clears the view, table and
  Prev/Next/Stop (the worker already stopped the old source); a failure after a frame
  keeps the last picture.
- FFmpeg prints its own stderr line (e.g. `moov atom not found`) on a broken `.mp4`
  before our one-sentence error; it cannot be silenced from the process.
- `model.weights` is resolved against the **current working directory**, while
  `CONFIG_PATH`, `rules.file` and `HANDLERS_PATH` are resolved against `detect.py`.
  Run from the project root, or put an absolute path in `config.yaml`. The app's model
  list reads `PROJECT_ROOT / "models"` but writes `models/<entry>` — relative again.
- `--conf` below `conf_debug` pulls `conf_debug` down with it. Without that the
  flag would silently show exactly what `0.25` already showed, and the JSON would
  hold no `"debug": true` entry at all.
- `core/events.py` keeps its registry in module state. Anything that registers
  handlers and hands control back calls `clear()` itself; `main`, `run_stream` and
  `PipelineWorker.stop` do it after a stream whose rules call handlers.
- `handlers.py` runs on the detection loop (the worker thread in the app): a slow
  handler slows the video by the same amount. In the app a photo's `@on_detect`
  handlers fire once, on its first display — not on Prev/Next back to it or the slider
  (a model or class change re-runs the photo and fires them again).
- Renaming `configure_console`, `CONFIG_PATH`, `EXIT_USAGE`, `PROJECT_ROOT`
  or `prepare_rules` in `detect.py` breaks `bench.py`, `scripts/grab.py`,
  `scripts/export_openvino.py`, `app.py` or `ui/`.
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
