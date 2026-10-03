# Інтерфейси — фаза 4

Спершу — правила проєкту, які з коду не виведеш. Далі — межі, вирішені в
специфікації (скопійовано з `spec.md`). Після кожного таска сюди дописується, що він
реально побудував (розділ «Побудовано»).

## Правила проєкту

- Інтерпретатор — лише `venv\Scripts\python` (Python 3.11). Ніколи не `python`: системний
  3.7.3 не чіпати.
- Тести: `venv\Scripts\python -m pytest -q` (на старті фази 4 — 324 проходять). Один файл:
  `venv\Scripts\python -m pytest -q tests\test_<module>.py`. Нові тести фази 4 — у
  файлах `tests/test_training_<module>.py`.
- `CLAUDE.md` у корені — опис репозиторію після фази 3: конвенції, пастки, шви тестів.
  Прочитай розділи «Code conventions», «Pitfalls», «Tests» перед першою правкою.
- **Жоден тест і жоден агент не відкриває справжню камеру, не запускає `app.py` (крім
  `--help`), не запускає Label Studio і не ходить у мережу.** Не ставити `label-studio`,
  `fiftyone`; не викликати справжній `kaggle`. Справжній `kaggle` CLI і Label Studio —
  тільки в тестах-заглушках (фейковий exe / підмінена функція).
- Залежності: `kaggle` — у новий `requirements-training.txt` (таск 01 його створює, але
  **не встановлює**: код не імпортує пакет `kaggle`, а викликає exe як підпроцес).
  Будь-якої іншої відсутньої залежності — повертай `BLOCKED`, не встановлюй.
- Жодного `cv2.imread`/`cv2.imwrite`/`cv2.VideoCapture` напряму — читання відео через
  `core.source.Source` (вже має обхід кирилиці), запис зображень `cv2.imencode` +
  `Path.write_bytes`, читання `np.fromfile` + `cv2.imdecode`.
- Числа, які користувач крутив би у фазі 4, — у `training/training.yaml` і датакласі
  `training/settings.py` (кожен ключ обов'язковий; відсутній → `TrainingConfigError`
  з назвою ключа; невідомий → попередження в лог). Не в `config.yaml`, не в `core/config.py`.
  Тести беруть значення з власної фікстури, не копіюють з `training.yaml`.
- `core/`, `ui/`, `detect.py`, `app.py`, `bench.py`, `scripts/` — **без змін**. `training/`
  імпортує `core/` і `detect` (`configure_console`, `CONFIG_PATH`, `EXIT_USAGE`,
  `PROJECT_ROOT`); `core/` ніколи не імпортує `training/`.
- Будь-який модуль `training/`, що імпортує `ultralytics` (прямо чи через
  `core.detector.Detector`), робить `import core.detector` своїм першим проєктним
  імпортом, а `ultralytics` — ліниво всередині функції. Виняток: `training/kaggle/train.py`
  — він працює на Kaggle, де `core/` нема; але в smoke-режимі локально він не ходить у
  мережу (виставляє `YOLO_OFFLINE=1` сам, до імпорту ultralytics).
- Помилка використання в кожній команді `training/`: одне речення в stderr, код
  `EXIT_USAGE` (2), без traceback; `configure_console()` на старті `main`.
- Мережа дозволена лише в: `training/label_studio.py setup` (pip у `venv-labelstudio`),
  мережевих підкомандах `training/kaggle_run.py` (через exe `kaggle`, і тільки з `--yes`),
  і в `training/kaggle/train.py` на Kaggle (pip там). Усе інше в `training/` — офлайн.
- Дані користувача — під `data/training/` (gitignored разом з `data/`): `frames/`,
  `exports/`, `build/`. `venv-labelstudio/` — додати в `.gitignore`.
- Не редагувати: `ARCHITECTURE.md`, `PROJECT_PROMPT.md`, `docs/`, `.autopilot/`, `CLAUDE.md`.
- `config.yaml` містить незакомічену зміну користувача (`model.weights` → OpenVINO,
  рядок `.pt` закоментований). Не чіпати і не комітити `config.yaml`.
- UTF-8 файли редагувати Write/Edit, не PowerShell `Set-Content`. Bash-інструмент тут
  ламається на heredoc — Python-скрипти клади у файл і запускай через PowerShell.
- Код, коментарі, логи, посібник — англійською. Коміти — Conventional Commits, англійською.

## Межі, вирішені в специфікації

| Модуль | Володіє | Виставляє | Ховає |
|---|---|---|---|
| `training/settings.py` | схема `training.yaml` | `load_training(path) -> TrainingConfig` (frozen dataclasses), `TrainingConfigError(ValueError)`, `TRAINING_CONFIG_PATH` | правила ключів |
| `training/classes.py` | порядок 82 імен | `class_names(base_names: dict[int,str], custom: list[str]) -> list[str]`; `ValueError`, якщо кастомне ім'я вже є серед базових | — |
| `training/extract_frames.py` | відео → кадри | `main(argv) -> int`, `extract(video, out_dir, step) -> int` | читання відео (через `core.source.Source`), запис через `imencode` |
| `training/label_studio.py` | все про Label Studio | `main(argv) -> int` з підкомандами `setup`, `start`, `config`; `labeling_config(classes) -> str` | шляхи venv, змінні середовища |
| `training/prelabel.py` | модель → завдання LS з predictions | `main(argv) -> int`, `tasks(images, detections_by_image, classes, image_root) -> list[dict]` | формат JSON Label Studio |
| `training/build_dataset.py` | збірка датасету | `main(argv) -> int`, `read_ls_export(path) -> list[Item]`, `pseudo_labels(...)`, `split(items, val_fraction) -> (train, val)`, `write_build(...) -> Path` | формат YOLO-рядків, IoU |
| `training/kaggle_run.py` | `kaggle` CLI | `main(argv) -> int` з `check`, `upload`, `train [--rough]`, `status`, `fetch`; `KAGGLE_EXE` (модульна змінна, тести підміняють на фейковий exe) | `kernel-metadata.json`, `dataset-metadata.json`, тимчасові теки |
| `training/kaggle/train.py` | навчання (на Kaggle і в smoke) | `main(argv) -> int` з `--data-root`, `--coco-root` (опц.), `--out`, `--smoke` | конвертація COCO → YOLO, `metrics.json` |
| `training/evaluate.py` | порівняння моделей | `main(argv) -> int` | виклик `YOLO.val` |
| `training/README.md` | посібник | — | — |

### Формат build-теки (спільний для 03, 04, 05)

```
data/training/build/<name>/
  data.yaml        # path: . ; train: images/train ; val: images/val ; names: {0: person, …, 80: pen, 81: flower}
  images/train/*.jpg   labels/train/*.txt     # YOLO: "<cls> <cx> <cy> <w> <h>" нормовані 0..1; порожній .txt = негатив
  images/val/*.jpg     labels/val/*.txt
  training.yaml    # копія training/training.yaml на момент збірки
  <base_weights файл>  # напр. yolo26n.pt — з training.base_weights
  manifest.json    # {"name", "mode": "full"|"rough", "classes": [...82 або 2], "counts": {"train": {cls: n}, "val": {...}},
                   #  "images": {"train": n, "val": n}, "negatives": n, "sources": {"own": n, "extra": n}}
```

`--rough`: `names` = лише `training.classes` з ID 0..k-1, без псевдорозмітки і `--extra`.

### Вихід навчання (спільний для 04, 05)

`training/kaggle/train.py --out DIR` пише `DIR/best.pt` і `DIR/metrics.json`:
`{"mode", "epochs", "imgsz", "names": [...], "val_own": {"mAP50": x, "per_class": {cls: mAP50}},
"coco": {"base_mAP50": x|null, "trained_mAP50": x|null}}` (`coco` — null без `--coco-root`).
`kaggle_run fetch --name N` кладе їх як `models/N.pt` і `models/N.metrics.json`.

Шви для тестів: `main(argv)` кожного скрипта + чисті функції (`labeling_config`,
`tasks`, `read_ls_export`, `split`, `class_names`, конвертація COCO). Модель у тестах —
`StubDetector` як у `tests/test_detect_cli.py`; `kaggle` — фейковий exe через
`KAGGLE_EXE`; Label Studio — не запускається. Один subprocess-smoke тест: повний
`kaggle/train.py --smoke` на `models/yolo26n.pt` з пасткою сокетів (пропуск, якщо
ваг нема), далі `export_openvino` на результат і `Detector` з 82 іменами.

## Побудовано

### З таска 01 — основа

- `training.settings`: `load_training(path=TRAINING_CONFIG_PATH) -> TrainingConfig`;
  `TrainingConfigError(ValueError)`; `TRAINING_CONFIG_PATH = training/training.yaml`.
  `TrainingConfig(classes: list[str], base_weights: str, frames: FramesConfig(step,
  target_total), dataset: DatasetConfig(val_fraction, pseudo_conf, pseudo_iou_drop,
  internet_fraction, min_negative_fraction, seed), coco: CocoConfig(train_images,
  val_images), train: TrainConfig(epochs, imgsz, batch), rough: RoughConfig(epochs),
  kaggle: KaggleConfig(username, dataset_slug, kernel_slug, coco_dataset))`, усе frozen.
  Немає файлу → `FileNotFoundError("training config file not found: …")`. `settings.py`
  нічого не імпортує з `core/` — придатний для `training/kaggle/train.py` на Kaggle.
- `training.classes.class_names(base_names: dict[int,str], custom: list[str]) -> list[str]`;
  `ValueError` з назвами при збігу імен або якщо ID базових не 0..N-1.
- `training.extract_frames`: `main(argv=None) -> int` (`--video`, `--out`, `--force`),
  `extract(video, out_dir, step) -> int`; модульні `FRAMES_ROOT` (`data/training/frames`),
  `TRAINING_CONFIG_PATH`, `PROJECT_ROOT` — тести їх підміняють. Запуск як скрипт або `-m`.
  Рядки: `wrote N frames to <dir>`, `total M frames in data/training/frames (target ~T)`.
- Тести: `tests/test_training_settings.py` експортує `TRAINING_SCHEMA`,
  `training_text(overrides, without)`, фікстуру `write_training` — інші тести фази 4
  імпортують `training_text` звідти (не копіюють значення з `training.yaml`).
- `tests/test_training_boundaries.py`: `NETWORKED = {kaggle_run.py, label_studio.py,
  kaggle/train.py}`; кожен інший `training/*.py` сканується автоматично на мережеві імпорти.
