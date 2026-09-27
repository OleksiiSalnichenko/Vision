# Інтерфейси — фаза 3

Спершу — межі, вирішені в специфікації (скопійовано дослівно з `spec.md`). Нижче —
правила проєкту, які з коду не виведеш. Після кожного таска сюди дописується, що він
реально побудував (розділ «Побудовано»).

## Правила проєкту

- Інтерпретатор — лише `venv\Scripts\python` (Python 3.11). Ніколи не `python`: системний
  3.7.3 не чіпати.
- Тести: `venv\Scripts\python -m pytest -q` (на старті фази 3 — 188 проходять). Один файл:
  `venv\Scripts\python -m pytest -q tests\test_<module>.py`.
- `CLAUDE.md` у корені — опис репозиторію після фази 2: конвенції, пастки, шви тестів.
  Прочитай розділи «Code conventions», «Pitfalls», «Tests» перед першою правкою.
- **Жоден тест і жоден агент не відкриває справжню камеру** (`camera:0`, голе `0`,
  `grab.py`, `app.py --source camera:0`). Помилковий шлях — `camera:9`, решта — заглушки.
- Qt у тестах — лише `QT_QPA_PLATFORM=offscreen`. Жодного вікна на екрані користувача.
- Жодного `cv2.imread`/`cv2.imwrite` — `np.fromfile`+`cv2.imdecode`, `cv2.imencode`+
  `Path.write_bytes` (кирилиця в шляхах).
- Жодного числа, яке користувач захотів би крутити, у коді: воно в `config.yaml` + датаклас +
  `_RULES` у `core/config.py` + `tests/conftest.CONFIG_SCHEMA`. Тести беруть значення з
  `conftest.schema_value` / `config_text`, не копіюють з `config.yaml`.
- `core/` не імпортує `ui/` і Qt; не друкує нічого поза `core/output.py`; без `argparse`.
- Мережа — лише `pip install` і `scripts/fetch_models.py`. `ultralytics` імпортують лише
  `core/detector.py`, `core/tracker.py`, `scripts/export_openvino.py`, ліниво.
- Залежності: `PySide6` і `pytest-qt` додає таск 05 у `requirements.txt` і ставить у venv
  (`venv\Scripts\python -m pip install -r requirements.txt`). Будь-якої іншої залежності
  бракує — повертай `BLOCKED`, не встановлюй.
- Не редагувати: `ARCHITECTURE.md`, `PROJECT_PROMPT.md`, `docs/`, `.autopilot/`, `CLAUDE.md`.
- `config.yaml` містить незакомічену зміну користувача (`model.weights` → OpenVINO,
  рядок `.pt` закоментований). Не повертати і не комітити її; таск 01 додає лише ключ
  `display.color`, решту файлу лишає як є.
- UTF-8 файли редагувати Write/Edit, не PowerShell `Set-Content`.
- Код, коментарі, логи, написи UI — англійською. Коміти — Conventional Commits, англійською.

## Межі, вирішені в специфікації

| Модуль | Володіє | Виставляє | Ховає |
|---|---|---|---|
| `core/pipeline.py` (новий) | порядок кадру для фото і потоку; єдиний викликач `is_debug`; виконання дій правил | `prepare_rules(rules_path: Path, handlers_path: Path) -> RuleSet`; `StillResult(canvas, drawn, near_miss, detections)` (frozen; `detections` — усі від `conf_debug`); `process_still(frame, detector, cfg, want_color) -> StillResult`; `resplit_still(frame, detections, cfg, want_color) -> StillResult` (без моделі — для повзунка); `save_still(source: str, result, cfg) -> list[Path]`; `StreamResult(canvas, drawn, near_miss, target, events, status)` (frozen); `StreamSession(detector, cfg, rule_set, fps, frame_size, is_video, on_log: Callable[[Event], None], want_color)` — контекстний менеджер: `step(frame) -> StreamResult`, `click(point)`, `retune(cfg, want_color)` (новий сеансовий конфіг: поріг → `Tracker.set_conf`, дисплей, колір; треки не скидаються), `set_detector(detector)`, `close() -> list[Path]` (ідемпотентний), `frames`, `fired`. `want_color` у CLI = `args.color or cfg.display.color` | трекер, ціль, двигун правил, `StreamWriter`, FPS-вікно, `_act`, `_status`, `_add_colors` |
| `detect.py` | прапорці, консоль, коди виходу | те саме, що зараз: `main`, `parse_args`, `with_overrides`, `process`, `run_images`, `run_stream`, `prepare_rules(cfg)` (обгортка, читає `HANDLERS_PATH` у момент виклику), `Window`, `configure_console`, `CONFIG_PATH`, `HANDLERS_PATH`, `PROJECT_ROOT`, `EXIT_*` | — |
| `core/tracker.py` | + межі ByteTrack на льоту | + `Tracker.set_conf(conf: float)` | як ByteTrack зберігає аргументи |
| `core/detector.py` | + імена класів моделі, фільтр класів на льоту | + `Detector.names -> dict[int, str]`, + `Detector.set_classes(classes: list[str]) -> None` | модель |
| `core/config.py` | + запис значень у файл; + ключ `display.color` | + `save_values(path, values: dict[str, Any]) -> None`, `ConfigError`; `DisplayConfig.color: bool` | порядкове редагування, тимчасовий файл |
| `ui/worker.py` | модель, джерело, сеанс — у фоновому потоці | `PipelineWorker(cfg, detector_factory, source_factory)` (QObject). Слоти: `load_model()`, `open_source(spec)`, `stop()`, `set_paused(bool)`, `click(x, y)`, `set_conf(float)`, `commit_still()` (переписати файли поточного фото — коли повзунок відпущено), `show_index(i)` (тека: Prev/Next), `apply(cfg)` (новий сеансовий `Config`; робітник сам вирішує: перезавантажити модель, `set_classes` чи лише передати конфіг у сеанс). Сигнали: `model_ready(names: dict)`, `model_failed(str)`, `frame_ready(FramePayload)` (фото і потік), `event(str)`, `failed(str)`, `finished(str)` | цикл кадрів, прапорці стоп/пауза, кеш фото |
| `ui/view.py` | показ кадру і клік | `FrameView` (віджет): `show_image(ndarray)`, сигнал `clicked(x, y)` у пікселях кадру; `to_image_point(...)` — чиста функція | масштабування, поля |
| `ui/main_window.py` | вікно: джерела, перегляд, повзунок, таблиця, події, рядок стану | `MainWindow(cfg, worker_factory)` | розкладку |
| `ui/settings_panel.py` | панель налаштувань | `SettingsPanel(cfg, models_dir)`; `set_class_names(names)`; сигнали `changed(Config)`, `save_requested()` | віджети |
| `app.py` | точка входу | `main(argv=None) -> int` | — |

`FramePayload` (frozen dataclass у `ui/worker.py` — дані для UI-потоку, не віджет):
`canvas` (ndarray-копія), `drawn: list[Detection]`, `near_miss_count: int`,
`target_track_id: int | None`, `index: int`, `total: int` (0 — невідомо, камера),
`fps: float`, `source: str`, `is_stream: bool`.

**Шви для тестів** — два, обидва вже є в репозиторії за духом:

1. **`core.pipeline`** — зі `StubDetector` і синтетичними кадрами, як `test_detect_cli`
   сьогодні. Сюди ж — що `detect.py` поводиться як раніше (наявні тести).
2. **`ui.worker.PipelineWorker`** з `detector_factory`/`source_factory`-заглушками,
   offscreen, через `qtbot.waitSignal`. Вікно — через `MainWindow` з тим самим
   робітником-заглушкою: клік → `click`, повзунок → `set_conf`, закриття → `stop` і
   `Source.close`.

Плюс чисті функції (`to_image_point`, `save_values`) напряму.

## Побудовано

(поки нічого)
