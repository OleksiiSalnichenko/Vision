<!-- autopilot:start -->
# Vision

Local, fully offline object detection. A still image goes in; for every detected
object the app reports class, bounding box, and the offset of the object's centre
from the centre of the frame. Laptop first (Intel CPU, no CUDA), Raspberry Pi later.

Design of record: `ARCHITECTURE.md`. Current scope: project phases 0, 0.5 and 1.

## Language policy

Code, comments, log messages, README and UI strings are **English**. Conversation
with the user is Ukrainian.

## Commands

| Command | What it does |
|---------|------------|
| _(not set up yet — phase 0)_ | Install dependencies |
| _(not set up yet — phase 1)_ | Run detection on an image |
| _(none yet)_ | Run tests |

## Hard rules

- **No network at inference time.** The network is used exactly twice in the whole
  project: `pip install`, and the one-time weight download by `scripts/fetch_models.py`.
- **Weights load from an explicit local path.** `Detector.__init__` must raise
  `FileNotFoundError: run scripts/fetch_models.py first` when the file is missing.
  It must never fall back to an Ultralytics download.
- **`core/` must not import from `ui/`** or know how it was launched.
- **YOLO26 is NMS-free.** Do not add non-maximum suppression.
- Python 3.7.3 on this machine is system-owned and must keep working. Python 3.11
  is installed alongside it and not added to PATH.

## How Autopilot works here

Збірку веде навичка `/autopilot`. Вимоги, специфікація і таски — в `.autopilot/`.
Прогрес — `.autopilot/dashboard.html`. Правило: вимогу з `manifest.md`
може зняти тільки користувач.

Якщо робота триває — скажи «продовж автопілот»: стан підніметься
з `.autopilot/state.js`, перепитувати нічого не потрібно.
<!-- autopilot:end -->
