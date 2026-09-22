# 07 — Проводка потоку в `detect.py`, `handlers.py`, README

**Вимоги:** R01, R03, R07, R11, R14i, R28, R32, R37, R40i, R42, R48, R50, R52, R54
**Blocked by:** 02, 03, 04, 05, 06
**Зона:** `detect.py` · `handlers.py` · `README.md` · `tests/test_detect_cli.py`
**Хвиля:** 3
**Status:** ready

## Що має запрацювати

`detect.py --source clip.mp4` і `detect.py --source camera:0` показують живе
вікно з номерами треків і ціллю, клік блокує ціль, події з `rules.yaml` друкуються,
пишуть кадри і кличуть функції з `handlers.py`; на диск лягають JSONL і (для
файлу) `.mp4`. Фото й теки — рівно як у фазі 1. README пояснює все це
користувачу, включно з виміряними числами OpenVINO.

## З брифа, дослівно

> «Video and webcam branches in `Source`. ByteTrack for stable `track_id` across frames. Target selection: click an object to lock onto it, otherwise auto-select the one nearest the frame centre. Export to OpenVINO and measure the gain. `rules.yaml` …»
> «`core/aim.py` exists as a stub taking `aim(dx, dy)`»
> «`core/` must not import from `ui/` or know how it was launched.»
> «Stop after each phase and show me what to run.»
> «I am new to computer vision. When you make a technical choice, say in one line why»

Доповнення від користувача: живе вікно; у консоль лише події з `rules.yaml`;
`out/<ім'я>.jsonl`; для відеофайлу ще `out/<ім'я>_annotated.mp4`, для вебкамери
відео не пишеться. RTSP — відкладено.

## Розділи специфікації

Історії 1–11, 15–20, 36, 40–46; Рішення §13, §16; Шов 5. Перед початком прочитай
«Побудовано тасками» в `interfaces.md` — там точні сигнатури, які збудували 02–06.

## Що зробити

**`detect.py`** — лишається єдиною проводкою і єдиним викликачем `is_debug`.

- `main`: конфіг → `with_overrides` → `Source` → `Detector`, помилки використання
  як зараз (+ `RulesError`, `OSError` від камери на старті → одне речення, код 2).
  Далі `run_images(...)` для фото/теки (код фази 1 без змін поведінки) або
  `run_stream(...)` для `source.is_stream`.
- `--source` help: «image, folder of images, video file, or camera:N».
- `run_stream(source, detector, cfg, args, window) -> int`:
  - `load_rules(cfg.rules.file)` (шлях відносно кореня проєкту, як `CONFIG_PATH`);
    якщо `rule_set.calls()` не порожній — імпортувати `handlers` з кореня проєкту
    і перевірити, що кожне ім'я є в `events.names()`; ні → `unknown handler in
    rules.yaml: <name>`, код 2. Попередження на старті, якщо `class` правила і
    `cls` обробника не можуть збігтися (один раз, `log.warning`).
  - `Tracker(cfg)`, `Targeting(cfg)`, `RuleEngine(rule_set)`,
    `StreamWriter(..., video=` джерело — відеофайл, не камера `)`.
  - На кадр: `detector(frame)` → `tracker.update(frame, dets)` → поділ `is_debug`
    на `drawn` / `near_miss` → `--color` на `drawn` (як на фото) →
    `targeting.choose(drawn, size)` → `aim.aim(dx, dy)` для цілі →
    `status` (`target #id cls  dx dy  <стрілка>  <FPS>`, `target: lost`,
    `target: none`; FPS — ковзне середнє, вікно — константа модуля) →
    `draw.annotate(..., target, status)` → `engine.update(frame.time, drawn)` →
    для кожної події: `log` → `output.print_event`; `save_frame` →
    `output.write_event_frame` (розмічений кадр); `call` →
    `events.call(name, event.detection)` → `writer.write(...)` → `window.show`.
  - `events.emit` на потоці **не викликається** (лише `call` з правил).
  - Завершення: кінець файлу, `q`/`Esc`, `KeyboardInterrupt` → код 0; `OSError`
    від камери посеред роботи → повідомлення в stderr, код 1. Усі шляхи —
    `writer.close()` і `print_stream_summary`. `events.clear()` наприкінці, якщо
    підключався `handlers`.
- `Window`: режим потоку — `waitKey(1)`; `set_mouse_callback` на лівий клік →
  колбек, який проводка передає в `targeting.click(point, drawn_поточного_кадру)`.
  Без дисплея — як зараз: одне повідомлення, далі без вікна; `--no-window` на
  камері — до Ctrl+C.

**`handlers.py`** у корені — приклад для користувача: `@on_detect(cls="cell phone")`
`def on_phone(detection)` (ім'я з `rules.yaml` таска 04) — друк через `print` тут
дозволений, бо це код користувача, не `core/`. Англійський docstring: як додати
свою функцію і підключити її в `rules.yaml`.

**`README.md`** — розділ фази 2: команди для відео й камери, клік для цілі,
`rules.yaml` (умови, дії, дебаунс, зони в частках кадру), `handlers.py`, JSONL і
`.mp4`, експорт OpenVINO і перемикання одним рядком, таблиця «measured on this
laptop» з числами, які таск 05 записав в `interfaces.md` (с/кадр і FPS для `.pt`
і OpenVINO, прискорення). По одному рядку «чому» на кожен технічний вибір, без
лекцій. Нові пакети `lap` і `openvino` у розділі встановлення.

**Тести `tests/test_detect_cli.py`** (додати, наявні не ламати):

- `run_stream` зі `StubDetector` (фіксовані детекції з різним `conf`) і штучним
  джерелом-генератором з `is_stream=True` на 5 кадрів: JSONL має 5 рядків;
  near-miss — лише в JSONL з `debug: true`; події `appeared` з'являються в
  консолі один раз; `events.emit` не викликано (підписник-лічильник); `call`
  викликає зареєстровану функцію; `--no-window`.
- Невідоме ім'я в `call` → код 2 і повідомлення.

**Перевірити руками і записати у звіт:**

1. Відео: згенеруй 5-секундне відео з кадрів `data/test_images/cam0_*.jpg` +
   `bus.jpg` (скриптом поза репо, у `tmp`), прожени `detect.py --source <відео>
   --no-window` → JSONL, `.mp4`, підсумок.
2. `detect.py --source data/test_images/bus.jpg --no-window` — вивід як у фазі 1.
3. `detect.py --source camera:0 --no-window` — якщо камера є: кілька секунд,
   Ctrl+C не вийде з агентського шелу — тож натомість перевір, що помилка
   зайнятої/відсутньої камери дає код 2; живу камеру перевірить користувач.

## Критерії приймання

- [ ] Відеофайл: вікно/`--no-window`, JSONL рядок на кадр, `.mp4`, підсумок, код 0
- [ ] Консоль на потоці — лише події й підсумковий рядок
- [ ] Клік блокує ціль (перевірено кодом колбека й тестом `Targeting`; живий клік — користувач)
- [ ] `call` з `rules.yaml` кличе функцію з `handlers.py`; невідоме ім'я — код 2
- [ ] Фото й теки — поведінка фази 1 без змін, наявні тести зелені без правок
- [ ] README описує фазу 2 і містить виміряні числа OpenVINO
