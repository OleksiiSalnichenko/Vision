# 05 — Експорт в OpenVINO і вимір виграшу

**Вимоги:** R17, R18, R19, R20, R21, R41, R43, R44, R45, R46
**Blocked by:** 01
**Зона:** `core/detector.py` · `scripts/export_openvino.py` · `bench.py` · `tests/test_detector.py` · `tests/test_export.py` · `tests/test_bench.py` · `tests/test_offline_openvino.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Користувач одним офлайновим скриптом конвертує ваги в OpenVINO, перемикає детектор
на них одним рядком `config.yaml` і одним запуском `bench.py` бачить, у скільки
разів стало швидше. Типові ваги лишаються `.pt`.

## З брифа, дослівно

> «Export to OpenVINO and measure the gain.»
> «OpenVINO (laptop), NCNN or Hailo (Pi) | Same weights, different export format. One config line.»
> «Inference runs locally, on CPU, accelerated with OpenVINO (Intel's own runtime, roughly 2-3x faster than plain PyTorch on this hardware).»
> «the rest are estimates to be replaced by real measurements from `bench.py`»
> «Ultralytics silently downloads weights. … It must never fall back to the network.»
> «`n`/`s`/`m` are sizes of one model, not different models. Switching is one config line. Do not build abstraction around "model selection".»

## Розділи специфікації

Історії 22–28, 47; Рішення §6–§10; Межі: `core/detector.py`, `bench.py`, `scripts/export_openvino.py`.

## Що зробити

**`core/detector.py`**

- Перевірка шляху до імпорту `ultralytics` лишається, але пропускає і файл, і
  теку. Відсутній шлях, що закінчується на `_openvino_model` →
  `FileNotFoundError(MISSING_EXPORT_MESSAGE)`, `MISSING_EXPORT_MESSAGE =
  "run scripts/export_openvino.py first"`; інакше — незмінне
  `MISSING_WEIGHTS_MESSAGE`. Тека, в якій немає `*.xml`, — те саме
  `MISSING_EXPORT_MESSAGE` (недописаний експорт).
- Решта без змін: `YOLO(str(path))` сам вибирає бекенд. Жодних гілок «якщо
  OpenVINO» в інференсі. `bus.jpg` на теці OpenVINO дає ті самі класи, що й `.pt`.

**`scripts/export_openvino.py`** — `main(argv=None) -> int`

- Перший імпорт проєкту — `import core.detector` (офлайн-перемикачі); потім
  `from detect import CONFIG_PATH, EXIT_USAGE, configure_console`.
- `--weights PATH` (типово — `model.weights` з конфігу; мусить бути `.pt`, інакше
  одне речення і код 2), `--force`.
- Ціль — `<stem>_openvino_model/` поруч із `.pt` (так іменує Ultralytics). Уже є і
  без `--force` → `skip: <path>` і код 0. `--force` — видалити теку і експортувати
  заново.
- `YOLO(pt).export(format="openvino", imgsz=cfg.model.imgsz, half=False,
  int8=False, dynamic=False, device="cpu")`. Без `openvino` у venv — одне речення
  `openvino is not installed -- run: venv\Scripts\python -m pip install -r requirements.txt`,
  код 2. Нічого не ставить.
- Друк: `exported: <path> (imgsz 640, FP32)` і нагадування, що зміна
  `model.imgsz` вимагає повторного експорту, і рядок для `config.yaml`, який
  перемикає детектор.
- Відсутній `.pt` → `run scripts/fetch_models.py first`, код 2.

**`bench.py`**

- `--weights A [B …]` (`nargs="+"`). Кожні ваги: `Detector(dataclasses.replace(cfg,
  model=dataclasses.replace(cfg.model, weights=w)))`, ті самі кадри, той самий
  протокол (`bench.warmup`, `bench.runs`), блок звіту як зараз із рядком `model:`.
  Після всіх — `speedup vs first: <w>: 2.10x` на кожні наступні. Без прапорця —
  рівно як зараз. Відсутні ваги — одне речення, код 2.
- Відео чи камера як `--source` → `bench.py measures still images: pass an image
  or a folder`, код 2 (використати `Source(...).is_stream` з таска 02, а поки його
  немає — перевірити розширення через `core.source.IMAGE_EXTENSIONS`: тека або
  файл із таким розширенням; інакше ця помилка).
- Функції `one_pass`, `measure`, `report` зберегти (їх можуть імпортувати).

**Запустити по-справжньому і записати у звіт** (це вимір, заради якого таск):

1. `venv\Scripts\python scripts\export_openvino.py` → тека з'явилась.
2. `venv\Scripts\python scripts\export_openvino.py` вдруге → `skip`.
3. `venv\Scripts\python bench.py --source data/test_images/bus.jpg --weights models/yolo26n.pt models/yolo26n_openvino_model`
   → вивід повністю у звіт, числа — с/кадр, FPS, прискорення.
4. `venv\Scripts\python detect.py --source data/test_images/bus.jpg --no-window` на
   OpenVINO: прапорця для ваг у `detect.py` немає, тому тимчасово зміни рядок
   `model.weights` у `config.yaml`, запусти, **поверни назад** і переконайся, що
   `git diff config.yaml` порожній. Порівняй класи й кількість детекцій із `.pt`.
5. Під час кроків 1 і 3 мережа не потрібна: якщо щось із Ultralytics пробує
   мережу — це `BLOCKED` із виводом, не обхід.

**Телеметрія OpenVINO.** Разом з `openvino` у venv приїхав пакет
`openvino-telemetry` (таск 01). Бриф: «Fully offline at runtime». З'ясуй за
вихідним кодом у `venv\Lib\site-packages\openvino_telemetry\` і
`venv\Lib\site-packages\openvino\`, коли він надсилає дані (завантаження
моделі? `convert_model` під час експорту?) і що його вимикає. Вимкни його в
коді проєкту так само, як `core/detector.py` вимикає телеметрію Ultralytics — на
рівні процесу, до першого імпорту `openvino`, **не** через налаштування машини
(файл згоди в профілі користувача належить машині, не репозиторію). Додай у
`tests/test_detector.py` (або новий `tests/test_offline_openvino.py` — твоя зона)
підпроцесну перевірку в стилі `tests/test_offline.py`: імпорт `core.detector`,
потім `import openvino` і те, що в `openvino_telemetry` відповідає за надсилання,
не торкаються сокетів / телеметрія вимкнена. Якщо вимкнути на рівні процесу
неможливо — `DONE_WITH_CONCERNS` з одним реченням, що саме і де.

**Тести** (моделі не вантажать):

- `tests/test_detector.py`: відсутня `models/x_openvino_model` → `MISSING_EXPORT_MESSAGE`;
  порожня тека `*_openvino_model` → те саме; відсутній `.pt` → як раніше; і все
  ще до імпорту `ultralytics` (наявна пастка).
- `tests/test_export.py`: `main(["--weights", "missing.pt"])` → 2; `.onnx` замість
  `.pt` → 2; наявна тека без `--force` → `skip`, 0 (у `tmp_path`, без реального
  експорту: підмінити сам виклик експорту).
- `tests/test_bench.py`: відео як `--source` → 2; розбір `--weights` із двома
  значеннями; `report` друкує `speedup` (підмінений `Detector`, без моделі).

## Критерії приймання

- [ ] `models/yolo26n_openvino_model/` створено скриптом, повторний запуск — `skip`
- [ ] Детектор на теці OpenVINO працює, класи на `bus.jpg` ті самі, що на `.pt`
- [ ] `bench.py --weights A B` друкує обидва виміри і прискорення; числа у звіті
- [ ] Відсутня тека OpenVINO → `run scripts/export_openvino.py first`, код 2
- [ ] `config.yaml` після таска — без змін (типові ваги `.pt`)
- [ ] Нові тести зелені, уся суїта зелена
