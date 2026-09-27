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
| `detect.py` | прапорці, консоль, коди виходу | те саме, що зараз: `main`, `parse_args`, `with_overrides`, `process`, `run_images`, `run_stream`, `prepare_rules(cfg)` (обгортка, читає `HANDLERS_PATH` у момент виклику), `Window`, `configure_console`, `CONFIG_PATH`, `HANDLERS_PATH`, `PROJECT_ROOT`, `EXIT_*`; нове — `want_color(args, cfg)` | — |
| `core/tracker.py` | + межі ByteTrack на льоту | + `Tracker.set_conf(conf: float)` | як ByteTrack зберігає аргументи |
| `core/detector.py` | + імена класів моделі, фільтр класів на льоту | + `Detector.names -> dict[int, str]`, + `Detector.set_classes(classes: list[str]) -> None` | модель |
| `core/config.py` | + запис значень у файл; + ключ `display.color` | + `save_values(path, values: dict[str, Any]) -> None`, `ConfigError`; `DisplayConfig.color: bool` | порядкове редагування, тимчасовий файл |
| `ui/worker.py` | модель, джерело, сеанс — у фоновому потоці | `PipelineWorker(cfg, detector_factory, source_factory)` (QObject). Слоти: `load_model()`, `open_source(spec)`, `stop()`, `set_paused(bool)`, `click(x, y)`, `set_conf(float)`, `commit_still()` (переписати файли поточного фото — коли повзунок відпущено), `show_index(i)` (тека: Prev/Next), `apply(cfg)` (новий сеансовий `Config`; робітник сам вирішує: перезавантажити модель, `set_classes` чи лише передати конфіг у сеанс). Сигнали: `model_ready(names: dict)`, `model_failed(str)`, `frame_ready(FramePayload)` (фото і потік), `event(str)`, `failed(str)`, `finished(str)` | цикл кадрів, прапорці стоп/пауза, кеш фото |
| `ui/view.py` | показ кадру і клік | `FrameView` (віджет): `show_image(ndarray)`, сигнал `clicked(x, y)` у пікселях кадру; `to_image_point(...)` — чиста функція | масштабування, поля |
| `ui/main_window.py` | вікно: джерела, перегляд, повзунок, таблиця, події, рядок стану | `MainWindow(cfg, worker_factory)` | розкладку |
| `ui/settings_panel.py` | панель налаштувань | `SettingsPanel(cfg, models_dir)`; `set_class_names(names)`; `set_config(cfg)`; `config()`; сигнали `changed(Config)`, `save_requested()`; допоміжні `model_choices(models_dir, current)`, `is_openvino(weights)` | віджети |
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

### З таска 01 — підготовка `core/`

- `core.config.DisplayConfig.color: bool`; `_RULES["display.color"]`; `config.yaml` —
  `display.color: false`; `CONFIG_SCHEMA` — `display.color = True`
- `core.config.save_values(path: str | Path, values: dict[str, Any]) -> None` — крапкові
  ключі + `"classes"`; `ConfigError` з назвою ключа (невідомий, відсутній у файлі,
  відхилений `_RULES`, `classes` не `list[str]`); тимчасовий `.<name>.tmp` поруч →
  `load_config` → `os.replace`. Числа округлюються до 6 знаків
- `core.detector.Detector.names -> dict[int, str]` (властивість, копія);
  `Detector.set_classes(classes: list[str]) -> None` (`[]` = усі, невідоме ім'я →
  `ValueError`, фільтр не змінюється)
- `core.tracker.Tracker.set_conf(conf: float) -> None` — `track_high_thresh` і
  `new_track_thresh`; треки, id і нижня межа лишаються
- Тести: 202 проходять
- Ремонт 1: рядок ключа розбирається `_KEY_HEAD` + `_comment_start` (`#` — коментар лише
  після пробілу і поза лапками); `_checked_classes` — одне правило для load і save;
  список `classes` з порожніми рядками/коментарями між пунктами — `ConfigError`

### З таска 02 — спільний конвеєр

- `core.pipeline.prepare_rules(rules_path: Path, handlers_path: Path) -> RuleSet`
- `StillResult(canvas, drawn, near_miss, detections)` (frozen);
  `process_still(frame, detector, cfg, want_color) -> StillResult` — нічого не пише і
  **не викликає `events.emit`**: викликач емітить сам після `process_still` (`detect.process`
  — після друку) і **не** емітить після `resplit_still`
- `resplit_still(frame, detections, cfg, want_color) -> StillResult` — без моделі, вхідний
  список не мутується, колір у копіях
- `save_still(source: str, result, cfg, on_written: Callable[[Path], None] | None = None)
  -> list[Path]` — спершу зображення, потім json; колбек після кожного запису; вимкнене в
  конфігу пропускається
- `core.pipeline.StreamWriteError(OSError)` — єдиний `OSError`, який `StreamSession.step`
  кидає за свої записи (кадр події, файли `StreamWriter`). `OSError` від детектора,
  трекера, малювання чи handler-а летить далі як є. **Робітник UI ловить саме
  `StreamWriteError`** навколо `step`, не голий `OSError`
- `detect.py` більше не має атрибута модуля `draw`; тести підміняють `core.draw`/`core.output`
- `StreamResult(canvas, drawn, near_miss, target, events: tuple[Event, ...], status)` (frozen)
- `StreamSession(detector, cfg, rule_set, fps, frame_size | None, is_video, on_log,
  want_color)` — контекстний менеджер; `step(frame) -> StreamResult` (кидає `OSError`,
  коли файл не пишеться); `click(point)`; `retune(cfg, want_color)` — поріг, дисплей, колір
  з наступного кадру (конфіг уже відкритих файлів `StreamWriter` не міняється);
  `set_detector(detector)`; `close() -> list[Path]` ідемпотентний; атрибути `frames`, `fired`
- `detect.want_color(args, cfg) -> bool` = `args.color or cfg.display.color`;
  `detect.prepare_rules(cfg)` — обгортка, читає `HANDLERS_PATH` у момент виклику
- `is_debug` викликають лише `core/detector.py` (визначення) і `core/pipeline.py`

### З таска 03 — робітник (+ D01)

- `StreamSession.redraw() -> StreamResult` — останній кадр під поточний конфіг і захоплення
  цілі; без детектора, без правил, без запису; `events == ()`, `frames`/`fired` не
  змінюються; до першого `step` — `RuntimeError("no frame to redraw yet")`.
  `StreamSession.fps -> float` (лише читання). Ремонт 1: `redraw` не рахується кадром для
  відпускання цілі — `core.target.Targeting.choose(detections, frame_size, new_frame: bool =
  True)`, з `new_frame=False` лічильник втрати не міняється; поділ → колір → ціль → стан →
  накладка — лише в приватному `StreamSession._render`; `FramePayload.drawn` — копії
  `Detection`
- `core.output.format_event(event) -> str`, `format_summary(frames, events, paths) -> str`;
  `print_event` / `print_stream_summary` друкують саме їх
- `ui.worker.FramePayload(canvas, drawn, near_miss_count, target_track_id, index, total,
  fps, source, is_stream)` (frozen; `canvas` — копія)
- `ui.worker.PipelineWorker(cfg, detector_factory, source_factory, parent=None)`. Слоти:
  `load_model()`, `open_source(str)`, `stop()`, `shutdown()` (стоп + `thread().quit()`;
  UI ставить у чергу і потім `QThread.wait()`), `set_paused(bool)`, `click(float, float)`,
  `set_conf(float)`, `commit_still()`, `show_index(int)`, `apply(object)`
- Сигнали: `model_ready(object)` (dict[int, str]), `model_failed(str)`, `frame_ready(object)`,
  `event(str)`, `failed(str)`, `finished(str)`, `applied(object)` — `Config`, яким сеанс
  реально працює (після невдалої моделі чи невідомого класу — старі значення; панель
  повертається через `set_config`)
- `apply` зберігає `model.conf`/`conf_debug` від `set_conf`: поріг — лише `set_conf`.
  Невідомий клас → `failed("unknown class names in config: …")`
- Потік — одна черга-тік на кадр, команди виконуються між кадрами. На паузі `click` і
  `set_conf` одразу дають новий `frame_ready`. Будь-яка помилка кадру, крім запису, —
  `failed` і кінець потоку, застосунок живий

### З таска 05 — панель налаштувань і Qt

- Встановлено у venv: PySide6 6.11.2, pytest-qt 4.5.0 (`requirements.txt`). Тести Qt
  ставлять `QT_QPA_PLATFORM=offscreen` на початку модуля, до імпорту Qt
- `ui.settings_panel.SettingsPanel(cfg: Config, models_dir: str | Path, parent=None)`
  (QWidget). Сигнали: `changed(object)` — новий сеансовий `Config`; `save_requested()`.
  Методи: `set_class_names(names: dict[int, str])`, `set_config(cfg)` (повертає віджети,
  нічого не випромінює, імена класів моделі лишаються), `config() -> Config`
- Публічні віджети: `model_box`, `imgsz_box`, `classes_list`, `all_classes_label`,
  `color_check`, `center_line_check`, `save_button`
- `ui.settings_panel.model_choices(models_dir, current) -> list[str]` — записи
  `"<models_dir.name>/<entry>"`, поточна вага першою, якщо її немає на диску;
  `is_openvino(weights) -> bool`; `model_entry(models_dir, weights) -> str` — одне
  написання (`./`, зворотні слеші, абсолютний шлях усередині models_dir →
  `"<models_dir.name>/<file>"`). Передавати `models_dir = PROJECT_ROOT / "models"`.
  З OpenVINO панель повертає `imgsz` до стартового (з конструктора / останнього `set_config`)
- Класи з whitelist, яких модель не знає, лишаються в списку (позначені) —
  `set_classes` робітника дасть на них `ValueError`
