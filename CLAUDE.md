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
list, events, settings panel with Save to `config.yaml`). Built: phases 0, 0.5, 1, 2,
3 and the phase 4 tooling (`training/`: video → frames → Label Studio → dataset build →
Kaggle training → local comparison, plus the guide `training/README.md`), verified on
synthetic data only. The 82-class model (COCO's 80 + `pen`, `flower`) is not trained
yet: it needs the user's own frames and a Kaggle account (`training/README.md` «For
the agent» is the session order).

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
| `venv\Scripts\python -m pip install -r requirements-training.txt` | phase 4 extras: the `kaggle` CLI into the project venv (online; not installed yet — **ask first**) |
| `venv\Scripts\python training\extract_frames.py --video data/clip.mp4 --out out\frames --force` | every `frames.step`-th frame → `out\frames\clip_000000.jpg …` (a trial run; without `--out` it goes to `data\training\frames\<video>\`, which the build reads — keep test frames out of there); a non-empty folder needs `--force` |
| `venv\Scripts\python training\label_studio.py config` | print the Label Studio labeling XML for `training.classes` (offline) |
| `venv\Scripts\python training\label_studio.py setup` | create `venv-labelstudio\` + pip `label-studio` (online). **Only with the user's yes** |
| `venv\Scripts\python training\label_studio.py start` | Label Studio on 127.0.0.1:8080 serving `data\training`. **User only: a server** |
| `venv\Scripts\python training\prelabel.py --weights models\rough.pt --frames data\training\frames --skip-labelled data\training\exports\first50.zip` | model boxes as predictions → `data\training\tasks.json` (offline; `--frames` must be inside `data\training`) |
| `venv\Scripts\python training\build_dataset.py --export data\training\exports\all.zip --name first` | build `data\training\build\first\` (82 names, pseudo-labels from `model.weights`); `--extra DIR`, `--rough`, `--force` |
| `venv\Scripts\python training\kaggle_run.py check` | local: `kaggle` exe, key file exists (never read), `kaggle.username`; `ok` or one sentence per gap, exit 2 |
| `venv\Scripts\python training\kaggle_run.py upload --build first` | prints the plan only; `upload`/`train [--rough]`/`status`/`fetch --name N [--force]` send nothing without `--yes`. **`--yes` only with the user's yes** |
| `venv\Scripts\python training\evaluate.py --weights models\yolo26n.pt models\pen.pt --build first` | mAP50 / mAP50-95, P, R, F1, mean IoU per new class + `all` shared classes + s/frame, CPU, offline; writes `<output.dir>\confusion_<model>.png`; `--imgsz N` |
| `venv\Scripts\python -m pytest -q` | tests (545 pass, ~5.5 min) |
| `venv\Scripts\python -m pytest -q tests\test_rules.py` | one test file |
| `venv\Scripts\python -m pytest -q tests\test_ui_window.py` | one Qt test file (offscreen, no window, stub model and camera) |
| `venv\Scripts\python -m pytest -q tests\test_training_settings.py tests\test_training_boundaries.py` | the fast training checks (schema, offline/network import scan; ~3 s) |

Never plain `python`: the system interpreter is 3.7.3 and must stay untouched.
The default model is OpenVINO (`model.weights: models/yolo26n_openvino_model`, docs/adr/0021);
switching back to PyTorch is one line: `model.weights: models/yolo26n.pt`.
`data\training\exports\*.zip`, `build\first`, `models\rough.pt`, `models\pen.pt` exist only
once the user has brought data; until then those commands end in one sentence, exit 2.
`training\kaggle\train.py --data-root BUILD --out DIR --smoke` (1 CPU epoch, imgsz 64) is
the local proof a build trains; **never run it without `--data-root`** — that is Kaggle
mode and starts `pip install ultralytics==8.4.157`.

## Structure

```
detect.py            the detection CLI: flags, console, exit codes over core/pipeline.py
app.py               the desktop app entry point: loads config.yaml, builds MainWindow
bench.py             timing harness, warm-up discarded; stills only
handlers.py          the user's functions for {call: name} rule actions (@on_detect)
config.yaml          every number, threshold and path in the project
rules.yaml           stream rules: debounce, zones, rules (still images ignore it)
requirements.txt     openvino pinned ==2026.3.1 (see Pitfalls); PySide6, pytest-qt
requirements-training.txt  `kaggle` (unpinned; the CLI exe, no module imports the package)
training/            phase 4, run as scripts from the project root: settings, classes,
                     extract_frames, ls_names, loading, label_studio, prelabel,
                     build_dataset, kaggle_run, evaluate, kaggle/train.py,
                     training.yaml, README.md (the user's guide + «For the agent»)
venv-labelstudio/    Label Studio's own venv (Django pins) — gitignored, made by `setup`
core/                launch-agnostic modules: types, config, source, detector, tracker,
                     target, rules, geometry, draw, output, events, attributes, aim,
                     pipeline (the frame order both front ends run)
ui/                  PySide6 only: worker.py (QThread worker), main_window.py, view.py,
                     settings_panel.py
scripts/             fetch_models.py (only networked code), export_openvino.py, grab.py
models/              *.pt, *_openvino_model/ — gitignored; checksums.txt tracked
data/test_images/    inputs — gitignored
data/training/       gitignored (all of data/), created on first use: frames/<video>/<video>_<NNNNNN>.jpg,
                     exports/ (LS YOLO zips), tasks.json, build/<name>/ {data.yaml (path: .,
                     names 0..81), images/{train,val}, labels/{train,val} (empty .txt =
                     negative), training.yaml copy, base weights, manifest.json}
out/                 <stem>.json, <stem>_annotated.jpg; streams: <stem>.jsonl,
                     <stem>_annotated.mp4 (video only), events/<stem>_<rule>_<index>.jpg
                     — gitignored, overwritten; camera stem is camera_N
tests/               one file per module + test_detect_cli, test_pipeline, test_offline(_openvino,_ui),
                     test_bench, test_export, test_ui_{worker,window,settings,view,boundaries},
                     test_training_<module> (+ _boundaries, _smoke, _e2e, _train)
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
  config: …")`, filter unchanged). `info() -> ModelInfo(weights, size_mb, params, gflops)`
  (None = unknown; an OpenVINO folder loads the `.pt` beside it for params/GFLOPs, so it is slow).
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
  `set_detector(d)`; `close() -> list[Path]` idempotent; `frames`, `fired`, `fps`, `latency -> (last, mean)` detector seconds.
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
  total, fps, latency, latency_mean, source, is_stream)` (frozen; canvas and detections are copies; `total` 0 =
  camera). `PipelineWorker(cfg, detector_factory, source_factory, parent=None)` (QObject,
  owns model, source, still cache, `StreamSession`). Slots: `load_model()`,
  `open_source(spec)` (stops the old one; rules → weights → source, like `detect.main`),
  `stop()`, `shutdown()` (stop + `thread().quit()`), `set_paused(bool)` (video only),
  `click(x, y)`, `set_conf(float)`, `commit_still()` (rewrite the photo's files after the
  slider), `show_index(i)` (model once per photo, then `resplit_still` from cache),
  `apply(cfg)` (weights/imgsz changed → rebuild detector, stream keeps tracks; classes →
  `set_classes`; else redraw; keeps `model.conf/conf_debug` — threshold only via
  `set_conf`), `frame_shown()`. Signals: `model_ready(dict)`, `model_info(ModelInfo)` (after it; skipped for a detector
  without `info`), `model_failed(str)`,
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
  `WINDOW_TITLE`, `*_TEXT`, `COLUMNS`, `TARGET_MARK`. Objects are a `QTreeWidget` (`tree`): a row per
  object, children from `detail_lines`; a `metrics` tree (groups Speed / Frame / Model from
  `speed_rows`, `frame_rows`, `model_rows`); the Find box (`find_classes`, `find_result_text`) narrows
  the session `classes` through the normal apply path and restores them when cleared. Public widgets are attributes
  (`view`, `slider`, `tree`, `settings`, `status_label`, `notice_label`, buttons …).
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
- `training/training.yaml` — every phase-4 number: `classes` (new names, IDs 80…),
  `base_weights`, `frames.{step,target_total}`, `dataset.{val_fraction, pseudo_conf,
  pseudo_iou_drop, internet_fraction, min_negative_fraction, seed}`, `coco.{train_images,
  val_images}`, `train.{epochs,imgsz,batch}`, `rough.epochs`, `kaggle.{username (empty),
  dataset_slug, kernel_slug, coco_dataset}`. The runtime never reads it.
- `training/settings.py` — `load_training(path=TRAINING_CONFIG_PATH) -> TrainingConfig`
  (frozen: `classes, base_weights, frames, dataset, coco, train, rough, kaggle` sub-dataclasses),
  `TrainingConfigError(ValueError)` naming the key; missing file → `FileNotFoundError("training
  config file not found: …")`; unknown key only logged. Imports nothing from `core/` — its
  source text is embedded into the Kaggle script.
- `training/classes.py` — `class_names(base_names: dict[int,str], custom) -> list[str]`: base
  names in ID order, then `custom`; `ValueError` on a clash or base IDs not 0..N-1.
- `training/extract_frames.py` — `main(argv)` (`--video`, `--out`, `--force`), `extract(video,
  out_dir, step) -> int` via `core.source.Source(Path, None)` + `imencode`; `FRAMES_ROOT`
  (`data/training/frames`, imported by `prelabel`/`build_dataset`), `FRAME_SUFFIX`.
- `training/ls_names.py` — the one Label Studio name rule: `frame_name(ls_stem, frames=())`
  (exact frame on disk wins; prefix `<8 hex>-` / `<digits>-` / `<digits>__` stripped only when
  the rest is a frame on disk; empty `frames` → pattern alone), `disk_frames(root) -> set[str]`,
  `maybe_dated(ls_stem)` (warning when no frames on disk).
- `training/loading.py` — `load_model(make, weights)`: any load failure → one-line
  `ValueError("cannot load the model …")`; every model load in prelabel/build/evaluate.
- `training/label_studio.py` — `main(argv)`: `setup` (venv + pip; 1 on failure, 2 without
  `py`; `skip:` when installed), `start` (`--internal-host 127.0.0.1`, `NO_REPORTING` env,
  local-files root `TRAINING_ROOT`), `config`; `labeling_config(classes) -> str`;
  `IMAGE_NAME="image"`, `LABEL_NAME="label"`, `VENV_DIR`, `TRAINING_ROOT`, `PY_LAUNCHER`, `BIND_HOST`.
- `training/prelabel.py` — `main(argv)` (`--weights --frames [--out] [--skip-labelled EXPORT]`,
  default out `data/training/tasks.json`); `tasks(images: dict[Path,(w,h)],
  detections_by_image, classes, image_root) -> list[dict]` (`/data/local-files/?d=<rel>`,
  boxes in percent as `predictions`); `labelled_stems(export)` (any `labels/*.txt`, empty
  too), `labelled_frames(labelled, frames)` (checked against `FRAMES_ROOT` + `--frames`
  only, never `exports/`/`build/`). Threshold = `model.conf` via `conf_debug=conf`, no `is_debug`.
- `training/build_dataset.py` — `main(argv)` (`--export --name [--extra DIR] [--rough]
  [--force]`, exit 0/2); `Item(image, labels: tuple[Label,…]|None, extra=False)`, `Label =
  (cls_name, cx, cy, w, h)` normalised; `read_ls_export(path, classes, unpack_dir=None)`,
  `read_extra(path, classes)` (`classes.txt` or `data.yaml`, case-insensitive),
  `pick_extra(pool, own, fraction, seed) -> (picked, short)`, `pseudo_labels(items,
  detector, custom, conf, iou_drop)`, `split(items, val_fraction, seed, frames=())` (last
  block of each video → val), `write_build(out_dir, train, val, names, new_classes, mode,
  training_yaml, base_weights, force=False) -> Path`. Order in `main`: `_check_name` →
  config → base weights → export → `_one_each` (frame exported twice) → no-new-class check →
  model → write. Full mode: `model.weights` labels its classes at `pseudo_conf`, a box with
  IoU ≥ `pseudo_iou_drop` to a hand box dropped; `--rough`: IDs 0..k-1, no model, no
  `--extra`. `base_weights` resolves against `PROJECT_ROOT`. Extra images → `extra_NNNNN`.
- `training/kaggle_run.py` — `main(argv)`: `check` | `upload --build N` | `train [--rough]` |
  `status` | `fetch --name N [--force]`; the last four print a plan and exit 0 without
  `--yes`. Exit 2 usage (empty username, missing build, no `kaggle` with `--yes`), 1 the
  `kaggle` CLI failed. `KAGGLE_EXE: list[str]|None` (venv's `kaggle.exe`, then PATH; tests
  swap a fake), `KAGGLE_JSON` (existence only), `NOT_FOUND = r"\b404\b"` (`datasets status`
  non-zero = new dataset only with 404 in the output, else exit 1), `SETTINGS_SLOT` (the
  `_SETTINGS_SOURCE` line of `train.py` replaced by `settings.py`'s text; missing → exit 2),
  `BUILD_ROOT`, `MODELS_DIR`. `upload` writes `dataset-metadata.json` into the build and
  removes it in `finally`; `train` pushes a private GPU+internet script kernel reading the
  dataset (+ `kaggle.coco_dataset` unless rough); `fetch` → `models/N.pt` +
  `models/N.metrics.json`, prints sha256 and the export command.
- `training/kaggle/train.py` — `main(argv)` (`--data-root`, `--coco-root`, `--out`, `--smoke`);
  no args = Kaggle (pip `ULTRALYTICS_PIN`, finds `manifest.json` and
  `annotations/instances_train2017.json` ≤ 4 deep under `/kaggle/input`, writes
  `/kaggle/working`; errors re-raised for the kernel log) — locally one sentence, exit 2.
  Sets `YOLO_OFFLINE`/`YOLO_AUTOINSTALL` itself (no `core/` on Kaggle). `coco_labels(instances,
  names, count, seed)` maps COCO by category *name*; `no_font_download()` — the one
  `check_font` patch; mode from `manifest.json`. Output `best.pt` + `metrics.json` `{mode,
  epochs, imgsz, names, val_own: {mAP50, per_class}, coco: {base_mAP50, trained_mAP50}|null}`.
- `training/evaluate.py` — `main(argv)` (`--weights A [B …] --build N [--imgsz N]`, default
  `model.imgsz`); `val_set(build, model_names, work)` (val copy, labels renumbered by class
  name per model, absolute `path:`), `score(weights, build, imgsz, work, conf) -> Scores(ap,
  quality, confusion, names)` (mAP from `YOLO.val`; P/R/F1/IoU and the confusion counted by
  `match_boxes`/`tally` at `model.conf`, pairs at `MATCH_IOU` 0.5, class-agnostic, best IoU first;
  `confusion_png`; a class with no val label gets no quality row),
  `seconds_per_frame(weights, images, imgsz)` (`bench.warmup`/`runs`), `table(...)` (`all` =
  mean over classes every model scored, `-` = unknown/no box), `export_size(weights)` (OpenVINO
  `metadata.yaml`; mismatch with `imgsz` or non-square → exit 2 before loading).
- `training/README.md` — the user's guide (sections 1–9, troubleshooting table) and «For
  the agent»: the step order with **[ask]** marks. Keep it in step with the commands.
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

Phase 4 (`training/`, separate scripts, nothing in the runtime changes): `extract_frames`
→ the user labels in Label Studio (own venv, local files) → optional rough path
(`build_dataset --rough` → `kaggle_run upload/train --rough/status/fetch` → `prelabel` →
`tasks.json` back into LS) → `build_dataset` (hand boxes + pseudo-labels from
`model.weights` + optional `--extra`) → `kaggle_run upload`, `train`, `status`, `fetch` →
`evaluate` → `scripts/export_openvino.py --weights models/<N>.pt` → one line of `config.yaml`.
The 82-class layout: IDs 0–79 are the current model's names in its order
(`class_names(detector.names, training.classes)`), then `pen` = 80, `flower` = 81; COCO labels
and `evaluate` both map by class *name*, never by ID, so `rules.yaml`, `classes` and
`handlers.py` stay valid. A Label Studio export name goes through `ls_names.frame_name`
everywhere (prelabel and build can never disagree on which frame a label belongs to).

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
- **`training/` offline/networked split.** Networked: `label_studio.py` (`setup` pip only),
  `kaggle_run.py` (`kaggle` exe as a subprocess, only with `--yes`; `check` and every plan are
  local), `kaggle/train.py` (pip on Kaggle). Every other `training/*.py` is offline and
  imports no `socket`/`requests`/`urllib`/`http`/`kaggle`, nor a networked module except
  `tests/test_training_boundaries.ALLOWED_NETWORKED_IMPORTS` (`evaluate` →
  `training.kaggle.train` for `no_font_download`; `prelabel` → `training.label_studio` for the
  tag names); a new offline module is scanned automatically. `core/` never imports
  `training/` (same test). `training/` imports `core/` and `detect` (`configure_console`,
  `CONFIG_PATH`, `EXIT_USAGE`); a module loading `ultralytics` (directly or via
  `Detector`) imports `core.detector` first.

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
- Phase-4 numbers live in `training/training.yaml` + `training/settings.py` (same rule: every
  key required), never in `config.yaml`/`core/config.py`. Training tests take values from
  `tests/test_training_settings.training_text` / `TRAINING_SCHEMA` / fixture `write_training`.
- Every `training/` command: `configure_console()` first, a usage error is one sentence on
  stderr, exit 2, no traceback; exit 1 only for a failed external tool (`kaggle` CLI, pip/venv
  or Label Studio in `label_studio.py`).
- **No network outside `pip install`, `scripts/fetch_models.py` and the networked
  `training/` steps (see Architecture)** — not on streams,
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

`venv\Scripts\python -m pytest -q` → 545 passed (~5.5 min; run single files while working).
`tests/conftest.py` puts the project
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
12. `test_training_<module>` — `main(argv)` + pure functions; module paths (`FRAMES_ROOT`,
    `BUILD_ROOT`, `TRAINING_ROOT`, `MODELS_DIR`, `TRAINING_CONFIG_PATH`, `CONFIG_PATH`,
    `Detector`) monkeypatched **in each module separately** (they are copied by import);
    model = `StubDetector`; `kaggle` = a fake exe via `KAGGLE_EXE`; Label Studio never starts.
    `test_training_boundaries` — AST import scan + importing the networked modules under a
    socket/`Popen` trap. `test_training_smoke` (train.py `--smoke` → export_openvino →
    `Detector` with 82 names) and `test_training_e2e` (video → build → train → evaluate on
    synthetic data) — one subprocess each with sockets trapped, ~1–2 min each, skipped
    without `models/yolo26n.pt`.

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
- **Never run networked training commands (`kaggle_run … --yes`, `label_studio setup`,
  `pip install -r requirements-training.txt`) without the user's explicit yes in chat; never
  read or ask for `kaggle.json`** (`%USERPROFILE%\.kaggle\kaggle.json` is the user's API key;
  `check` tests existence only). Run the subcommand without `--yes` first and show its plan
  line. No agent runs `label_studio.py start` (a server), installs `label-studio`/`fiftyone`
  into `venv`, or runs `training\kaggle\train.py` without `--data-root` (Kaggle mode: pip).
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
- **Ultralytics downloads `Arial.ttf` on every `train`/`val`** (`check_det_dataset` →
  `check_font`), `YOLO_OFFLINE=1` or not. Call `training.kaggle.train.no_font_download()`
  before any local `YOLO.train`/`YOLO.val`; the smoke/e2e tests use an empty Ultralytics
  config dir so a cached font cannot hide the download.
- **Ultralytics resolves `data.yaml` `path: .` against the cwd**, not the yaml's folder. The
  build keeps `path: .` (portable to Kaggle); `evaluate.val_set` and `train.py` write a temp
  yaml with an absolute path. Do the same for any new `YOLO.val` on a build.
- **Label Studio `--host` only names the URL in links**; the socket binds to
  `--internal-host` (default 0.0.0.0). `start` passes `--internal-host 127.0.0.1`.
- `kaggle_run.NOT_FOUND` (`404` in the output of a failed `kaggle datasets status` = first
  upload → `create`, anything else → exit 1) is not yet checked against the real CLI; nor is
  anything on a Kaggle GPU (paths under `/kaggle/input`, pip, run time) — the first real run
  proves it. The `kaggle` package is not installed and not pinned yet.
- `requirements.txt` says `ultralytics>=8.4` while the Kaggle kernel pins
  `ultralytics==8.4.157` (`train.ULTRALYTICS_PIN`, the version here). Upgrading locally
  splits the two and can break the offline switches (8.4.157 reads `YOLO_OFFLINE` once).
- `training.base_weights` resolves against `PROJECT_ROOT`; `model.weights` (pseudo-labels,
  `prelabel --weights`, `evaluate --weights`) against the cwd — run from the project root.
- Label Studio may prefix exported names (`17-`, `17__`, `<8 hex>-`); `frame_name` needs the
  frames under `data\training\frames` to tell a prefix from a dated clip name
  (`20261003-desk`). Without them `build_dataset` warns and guesses.
- `build_dataset --force` empties the build folder (`rmtree`) — but only after the name,
  config, export and duplicate checks pass. `--name` must be one plain folder name.
- An OpenVINO export has one fixed `imgsz`; `evaluate` refuses a mismatch with `--imgsz`
  before loading. Changing `train.imgsz` means rebuild, retrain, `model.imgsz` and
  `export_openvino.py --force`.
- `kaggle_run train` trains on whatever build was uploaded last; the mode comes from that
  build's `manifest.json`, so `train --rough` must follow `upload --build rough`.
- Module paths in `training/` are imported copies (`FRAMES_ROOT` from `extract_frames` into
  `prelabel`/`build_dataset`, `TRAINING_ROOT` from `label_studio` into `prelabel`): a test
  must monkeypatch each importing module, not only the source one.

## How Autopilot works here

Збірку веде навичка `/autopilot`. Вимоги, специфікація і таски — в `.autopilot/`.
Прогрес — `.autopilot/dashboard.html`. Правило: вимогу з `manifest.md`
може зняти тільки користувач.

Якщо робота триває — скажи «продовж автопілот»: стан підніметься
з `.autopilot/state.js`, перепитувати нічого не потрібно.
<!-- autopilot:end -->
