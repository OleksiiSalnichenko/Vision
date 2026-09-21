# Vision — Architecture

Local, offline object detection. Laptop first, Raspberry Pi later.

Status: **design approved, not implemented.** No code exists yet.

---

## 1. Goal and constraints

Build a local application that detects objects with a camera and reports, for each
object: its class, a bounding box, and the offset of the object's center from the
center of the frame.

Hard constraints:

| Constraint | Consequence |
|---|---|
| Must run fully offline | Network is used twice only: `pip install`, and a one-time model download. No runtime network calls, ever. |
| Must eventually run on Raspberry Pi | The Pi, not the laptop, sets the performance budget. Model size is chosen for the Pi. |
| Personal / learning project, not commercial | Ultralytics AGPL-3.0 is acceptable. |
| Custom classes required later | The pipeline must support fine-tuning without restructuring. |

Explicitly **not** goals: face recognition (identifying a specific person),
instance segmentation, handwriting OCR, a C++ rewrite.

---

## 2. Target hardware

Development machine (measured):

- CPU: Intel Core i7-8550U, 4 cores / 8 threads, 1.8 GHz base
- RAM: 15.8 GB
- GPU: Intel UHD Graphics 620 (integrated)
- **No NVIDIA GPU, therefore no CUDA**
- Camera: HP Wide Vision FHD (built-in), plus an HP IR camera
- OS: Windows 11

Deployment target (not yet purchased): Raspberry Pi 5, optionally with a Hailo-8L
AI HAT. Exact model to be confirmed by the user.

The absence of CUDA is the single most important hardware fact. It means:

- **Training must happen in the cloud.** Kaggle (free P100, 30 GPU-hours/week,
  private datasets) is the chosen provider. Training locally on CPU would take
  6-10 hours where a GPU takes 15 minutes.
- **Inference runs locally**, on CPU, accelerated with OpenVINO (Intel's own
  runtime, roughly 2-3x faster than plain PyTorch on this hardware).

---

## 3. Technology stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | The whole ML ecosystem is Python. 3.11 has prebuilt wheels for every dependency, including OpenVINO and Pi builds. The system currently has 3.7.3, which is too old for modern PyTorch and must be left untouched. |
| Detection | Ultralytics YOLO26 | Current generation, released October 2025. NMS-free end-to-end architecture: constant-time inference regardless of how many objects are in frame. The nano size is accurate enough for this project and fast enough for the Pi. |
| Image I/O and drawing | OpenCV | Standard, fast, already a YOLO dependency. |
| Acceleration | OpenVINO (laptop), NCNN or Hailo (Pi) | Same weights, different export format. One config line. |
| GUI (phase 3) | PySide6 | Official Qt bindings for Python, LGPL. Real desktop widgets, packageable to .exe. |
| Annotation (phase 4) | Label Studio | Runs locally via pip. Data never leaves the machine. Exports YOLO format directly. |
| Training (phase 4) | Kaggle Notebooks | Free GPU, private datasets, sessions do not drop mid-run. |
| Config | YAML | Every tunable number lives in `config.yaml`, never as a constant in code. |

Language policy: **code, comments, log messages, README and UI strings are all in
English.**

---

## 4. Model decision

**One model, everywhere: YOLO26n.**

The `n` / `s` / `m` / `l` / `x` suffixes are not different models. They are the
same architecture at different capacities, sharing one API, one weights format,
one dataset format and one export path. Switching between them is a single line
in `config.yaml`.

Published figures (Ultralytics, ONNX on Intel Xeon @ 2.0 GHz):

| Model | mAP 50-95 | Params | CPU ONNX | Role |
|---|---|---|---|---|
| YOLO26n | 40.9 | 2.4 M | 38.9 ms | the working model, everywhere |
| YOLO26s | 48.6 | 9.5 M | 87.2 ms | fallback, downloaded and kept on disk |

Expected throughput for YOLO26n (first two rows derive from published numbers,
the rest are estimates to be replaced by real measurements from `bench.py`):

| Environment | Per frame | FPS |
|---|---|---|
| Laptop, PyTorch (phase 1) | ~110 ms | ~9 |
| Laptop, OpenVINO (phase 2) | ~39 ms | ~25 |
| Pi 5, NCNN | ~200 ms | ~5 |
| Pi 5 + Hailo AI HAT | ~30 ms | ~30 |

`n` is the only size that produces usable numbers in all four rows. It is chosen
because the Pi, not the laptop, is the binding constraint.

`yolo26s.pt` is downloaded as a fallback and kept on disk. Small objects such as
a pen are the hardest case for a nano model; if phase 4 shows `n` cannot handle
them, switching to `s` must not require a network connection.

Larger sizes (m, l, x) are more accurate but too slow on the Pi, so they are not
part of this design. Training a detector from scratch is not considered either:
reproducing the COCO pretraining would take days on eight A100 GPUs, while
transfer learning reuses that work for the cost of a 6 MB download.

---

## 5. How the detector works

Useful background for reading the code.

A model file is two things: an architecture (which layers, in what order) and
weights (~2.4 million numbers for YOLO26n). The weights are the learned
knowledge; they were produced once by Ultralytics by training on COCO (118,000
images, 860,000 hand-drawn boxes) for several days on 8x A100 GPUs. We download
the result.

One inference pass:

1. **Preprocess.** The image is letterboxed into a 640x640 square and normalised
   to 0..1. Input tensor: `[1, 3, 640, 640]`.
2. **Backbone.** Convolutional layers extract a hierarchy of features: edges in
   early layers, textures and parts in the middle, whole objects at the end.
   Resolution shrinks 640 -> 320 -> 160 -> 80 -> 40 -> 20 while semantic content
   accumulates.
3. **Neck.** Feature maps at three scales (80x80, 40x40, 20x20) are fused, so
   small and large objects are both visible.
4. **Head.** For each of ~8400 grid cells, predicts 4 box coordinates and a
   per-class confidence.
5. **Filtering.** Everything below `conf` is discarded.

YOLO11 and earlier needed a sixth step, NMS, to merge duplicate boxes for the
same object. **YOLO26 is NMS-free**: duplicate suppression is internal to the
model. This is why its latency does not grow with scene complexity.

COCO classes are fixed at 80. The head has exactly 80 outputs, so the model
physically cannot emit "pen". Adding custom classes (phase 4) means **transfer
learning**: keep the backbone, replace the head with one that has the right
number of outputs, and train on a few hundred custom images. The backbone
already knows what edges and shapes look like; only the naming is relearned.
That is why 500 images and 20 GPU-minutes suffice instead of 860,000 and three
days.

Consequence to remember: a fine-tuned model sees **only** its new classes. To
detect `person` and `pen` together, either include both in the training set, or
run two models in sequence.

---

## 6. Repository structure

```
D:\Projects\Vision\
├── ARCHITECTURE.md        this file
├── README.md
├── config.yaml            every tunable value
├── requirements.txt
├── .gitignore             venv/, models/*.pt, out/, data/
├── detect.py              CLI entry point (phase 1)
├── bench.py               timing harness
├── scripts\
│   ├── fetch_models.py    explicit weight download + checksums
│   └── grab.py            save frames from the webcam as images
├── core\
│   ├── __init__.py
│   ├── types.py           Detection, Frame dataclasses
│   ├── config.py          load and validate config.yaml
│   ├── source.py          Source: image / folder / video / webcam / RTSP
│   ├── detector.py        YOLO wrapper: frame -> list[Detection]
│   ├── geometry.py        box centres, offsets from frame centre
│   ├── attributes.py      dominant colour (opt-in)
│   ├── draw.py            boxes, crosshair, labels, offsets
│   ├── events.py          event bus and user callback registration
│   ├── output.py          JSON, annotated image, console
│   └── aim.py             servo stub: aim(dx, dy) — draws an arrow for now
├── data\test_images\      user-supplied photos
├── models\                weights + checksums.txt
└── out\                   annotated images and JSON results
```

Roughly 700 lines for phase 1.

The point of this split is that **every later phase adds a file rather than
rewriting one**:

| Phase | Added | Rewritten |
|---|---|---|
| 2 — video | `core/tracker.py`, `core/rules.py`, a video branch in `source.py` | nothing |
| 3 — app | `ui/` (PySide6, imports `core/` as a library) | nothing |
| 4 — custom classes | `training/` | one config line |
| 5 — Pi | `scripts/export_ncnn.py`, web UI | one line in `detector.py` |

`core/` must never import from `ui/` or know how it was launched. This is the
one structural rule that matters.

---

## 7. Module contracts

### `core/types.py`

```python
@dataclass
class Detection:
    cls_id: int            # model class index
    cls_name: str          # e.g. "person"
    conf: float            # 0..1
    bbox: tuple            # (x1, y1, x2, y2) in source-image pixels
    center: tuple          # (cx, cy)
    dx: int                # cx - frame_center_x, pixels; right is positive
    dy: int                # cy - frame_center_y, pixels; down is positive
    dx_pct: float          # dx as a fraction of half the frame width, -1..1
    dy_pct: float          # dy as a fraction of half the frame height, -1..1
    color: str | None      # dominant colour name, only when --color is set

@dataclass
class Frame:
    image: np.ndarray      # BGR, as OpenCV returns it
    source: str            # file path, or "camera:0"
    index: int             # 0 for a still image, frame number for video
```

`Detection` is the only type that crosses module boundaries. Every consumer
(drawing, JSON, events, future servo control) reads this and nothing else.

### `core/source.py`

```python
class Source:
    def __iter__(self) -> Iterator[Frame]
```

One interface over a single image, a folder of images, a video file, a webcam
index, and an RTSP URL. Phase 1 implements the first two. Everything downstream
is written against the iterator and does not know or care which is in use —
this is what makes phase 2 nearly free.

Default capture resolution is 1280x720, not 1080p: the extra pixels are scaled
to 640 by the model anyway, and decoding 1080p wastes CPU for nothing.

### `core/detector.py`

```python
class Detector:
    def __init__(self, cfg: Config)     # fails loudly if weights are missing
    def __call__(self, frame: Frame) -> list[Detection]
```

Responsibilities: load weights from an **explicit local path**, run inference,
filter by confidence, filter by the class whitelist, and delegate geometry.

Critical offline behaviour: Ultralytics silently downloads weights from GitHub
when given a bare name like `yolo26n.pt`. On a Pi with no network that becomes a
confusing crash. Therefore `config.yaml` stores a **path** (`models/yolo26n.pt`),
and `Detector.__init__` raises
`FileNotFoundError: run scripts/fetch_models.py first` if the file is absent. It
must never reach for the network.

### `core/events.py`

```python
@on_detect(cls="person")
def handler(det: Detection):
    ...
```

The user's extension point. Phase 1: a plain synchronous call, one per detection,
no rules and no debouncing. Phase 2 layers rule evaluation and debouncing on top
of this same bus without changing its signature.

### `core/aim.py`

A stub. `aim(dx, dy)` currently just draws an arrow on the frame. It exists so
that when real pan-tilt servos appear, the change is one new file and zero edits
elsewhere. Servo hardware is a future idea, not a current plan.

---

## 8. Data flow (phase 1)

```
image file
    |
  Source ----------------------------> Frame(image, source, index)
    |
  Detector (YOLO26n)                    ~8400 raw candidates
    |
  filter: conf >= 0.5, class in whitelist
    |
  geometry: box centre, dx/dy vs frame centre
    |
  attributes: dominant colour            [only with --color]
    |
    +--> draw    -> OpenCV window + out\<name>_annotated.jpg
    +--> output  -> out\<name>.json
    +--> events  -> user callback(Detection)
    +--> console -> one line per detection
```

Overlay contents: a red crosshair at the centre of the frame, a box around each
object, a small green cross at each object's centre, and `dx / dy` printed inside
the box. No line is drawn between the two centres — the numbers already carry
that information, and connecting lines clutter the frame as soon as several
objects are present. Labels can be switched off; with ten or more objects the
numbers overlap and become unreadable.

---

## 9. Configuration

```yaml
model:
  weights: models/yolo26n.pt
  imgsz: 640            # native training size; other values usually hurt accuracy
  conf: 0.5             # display and event threshold
  conf_debug: 0.25      # written to JSON but not drawn — shows near-misses

classes:                # whitelist; empty means all 80 COCO classes
  - person
  - cell phone
  - bottle
  - book
  - laptop

display:
  show_labels: true
  show_offsets: true
  crosshair: true

output:
  save_json: true
  save_image: true
  dir: out

capture:
  width: 1280
  height: 720
```

`conf_debug` matters more than it looks. Writing every detection down to 0.25
into the JSON, while drawing only those above 0.5, is the main debugging tool:
it shows what the model *nearly* saw, which is what you need when tuning the
threshold or diagnosing a miss.

---

## 10. Phases

One model throughout: YOLO26n. The phases move it along a path — stock, then
accelerated, then fine-tuned, then re-exported for the Pi. They are not
alternative models.

### Phase 0 — environment (~20 min, mostly downloads)

Install Python 3.11 alongside 3.7 (do **not** add it to PATH; 3.7 must keep
working). `git init`, `.gitignore`, venv inside the project, then
`ultralytics`, `opencv-python`, `pyyaml`, `numpy`, `scikit-learn`.

Done when `python -c "import torch, cv2, ultralytics"` succeeds.

### Phase 0.5 — weights

`python scripts/fetch_models.py` downloads `yolo26n.pt` (~6 MB) and
`yolo26s.pt` (~18 MB) into `models\`, records SHA256 in `models\checksums.txt`,
and prints a summary.

After this step the project never needs the network again until phase 4.

### Phase 1 — still images

Everything in sections 6-9 above.

```bash
python detect.py --source data/test_images/bus.jpg
```

Verification order, deliberately in this sequence:

1. A stock Ultralytics sample image. A failure here means a broken install, not
   a hard problem.
2. The user's own 10-20 photos. This is where the truth appears.
3. Flags: `--color`, confidence threshold, class whitelist.
4. `scripts/grab.py` to capture real frames from the actual webcam — this is
   what reveals lighting, focus and noise problems early.

Done when: dropping in a photo produces a window with boxes, centre dot,
crosshair and offsets; `out\*.json` contains the numbers; `bench.py` prints
seconds per frame. Acceptance is the user's visual judgement — no formal mAP
target for this phase.

### Phase 2 — video and real time

Video and webcam branches in `Source`. ByteTrack for stable `track_id` across
frames. Target selection: click an object to lock onto it, otherwise
auto-select the one nearest the frame centre. Export to OpenVINO and measure the
gain. `rules.yaml`: conditions (appeared / disappeared / present for N seconds /
entered a zone), actions (log line, save frame, call a function), and debouncing
(confirm over 3 consecutive frames, then 5 seconds cooldown).

Debouncing is not optional. A model oscillating around the threshold at 0.49/0.51
will otherwise emit hundreds of events in seconds.

Tracking exists here and not in phase 1 because a still image has no time axis.

### Phase 3 — desktop application

PySide6: open a file or camera, live view, settings, object list, threshold
slider. `ui/` imports `core/`, never the reverse.

### Phase 4 — custom classes

Only if YOLO26n's stock classes are insufficient — which they are for "pen" and
"flower", since neither is in COCO.

Method: shoot 10 minutes of video of the object from many angles, take every
20th frame (~900 images with natural variation in angle, blur and lighting),
annotate in Label Studio, export in YOLO format, fine-tune on Kaggle, download
`best.pt`.

Two rules that decide whether this works:

- **Shoot in the conditions the model will actually run in.** A pen photographed
  as a studio product shot on a white background teaches the model nothing about
  a pen lying at an angle on a cluttered desk, 2 metres away, 40 pixels tall,
  under a yellow lamp. This mismatch — domain gap — is the most common reason a
  tutorial works and a real project does not. Internet images may be mixed in at
  around 20% for variety, but the core of the set must be your own frames.
- **Include negative frames**: the desk with no pen, the room with no flowers.
  Without them the model finds pens everywhere.

Labour-saving trick: annotate the first 50 images by hand, train a rough model,
let it pre-annotate the remaining 450, then correct its mistakes. Saves roughly
70% of the time.

Before shooting anything, check whether the class already exists as a labelled
dataset (Roboflow Universe, Open Images V7 with 600 classes). A ready labelled
dataset is a pure win. Raw images scraped from a search engine are not — they
still have to be annotated by hand, so they save only the shooting, not the
tedious part.

### Phase 5 — Raspberry Pi and extras

Export to NCNN (or Hailo if the AI HAT is bought). Web UI on FastAPI, because a
Pi usually has no monitor and a browser over the LAN is the only convenient
interface. Then, optionally: OCR of printed text (EasyOCR / PaddleOCR /
Tesseract, all local) on cropped detections, and a local VLM (Moondream2,
Florence-2, Qwen2.5-VL 3B) behind a "describe this frame" button.

The VLM is worth being precise about: it is a 1.7-8 GB language model that takes
3-15 seconds per frame on this CPU. It is fine for a button press on a still
frame. It is not usable for streaming video on this hardware.

---

## 11. Out of scope

Decided against, deliberately:

| Item | Reason |
|---|---|
| Face recognition (identifying a specific person) | User dropped it. It is a separate subsystem — a face detector plus an embedding model plus a local identity database. |
| Instance segmentation | Boxes only. Polygon annotation is 3-5x slower than boxes and would dominate the effort in phase 4. Note the asymmetry: a polygon converts to a box, a box does not convert to a polygon. |
| Handwriting OCR | Local models are weak at it. Printed text only, and only in phase 5. |
| C++ | The ML stack is Python, and the model already runs as compiled C++ internally. If the Pi runs out of headroom, only the inference layer gets rewritten, not the application. |
| Servo hardware | A future idea. `core/aim.py` is a stub so that adding it later costs one file. |
| `rules.yaml` in phase 1 | Deferred to phase 2, where debouncing makes it meaningful. |

---

## 12. Known risks

1. **No CUDA.** Heavy models cannot run in real time here, on the laptop or the
   Pi. The plan accounts for this by choosing YOLO26n and by training in the
   cloud.
2. **A pen is a hard class.** Small, thin, low contrast against a desk. May need
   `imgsz: 960`, or `yolo26s`, or simply shooting from closer. This is the most
   likely place for the plan to need adjusting.
3. **Domain gap.** Internet datasets do not match the user's frames. Own
   footage is mandatory for custom classes.
4. **Pi 5 without an accelerator runs only nano-sized models.** With a Hailo-8L
   AI HAT (~$70) it reaches roughly 30 FPS. The exact Pi model is still
   unconfirmed by the user.
5. **Silent weight downloads.** Ultralytics fetches from the network by default.
   Guarded by explicit paths and a loud `FileNotFoundError`. Worth re-checking
   after any dependency upgrade.
6. **Dominant colour may prove useless.** For a person it returns the T-shirt
   colour; for a flower, half the pot and the background. It lives behind
   `--color` in its own module so that deleting it costs one command.

---

## 13. Sources

- [Ultralytics — YOLO26 benchmarks](https://docs.ultralytics.com/compare/yolo26-vs-yolo11)
- [Ultralytics — end-to-end NMS-free detection](https://docs.ultralytics.com/guides/end2end-detection)
- [Ultralytics — model export formats](https://docs.ultralytics.com/modes/export)
- [Ultralytics — training on a custom dataset](https://docs.ultralytics.com/modes/train)
