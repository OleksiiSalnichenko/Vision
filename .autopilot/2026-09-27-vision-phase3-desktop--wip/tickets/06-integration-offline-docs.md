# 06 — Налаштування у вікні, «Save to config.yaml», офлайн-доказ, README

**Вимоги:** R01, R08, R16i, R16i.1, R20, R22, R23, R03, R34i, R29, R31
**Blocked by:** 04, 05
**Зона:** `ui/main_window.py` · `README.md` · `tests/test_offline_ui.py` · `tests/test_ui_boundaries.py` · `tests/test_ui_window.py`
**Хвиля:** 5
**Status:** ready

## Що має запрацювати

1. **Панель налаштувань у вікні.** `SettingsPanel` (таск 05) вбудовується в
   `MainWindow` (правий бік, завжди видима). `changed(cfg)` → `worker.apply(cfg)` — одразу,
   без кнопки «Apply». `model_ready(names)` → `set_class_names`. Модель не завантажилась
   (`model_failed`) → повідомлення + `set_config` зі старим конфігом. Поки модель
   перевантажується — «Loading model…» у рядку стану. Повзунок і панель — один сеансовий
   `Config`. Невідоме моделі ім'я класу (панель лишає його позначеним, `set_classes` дає
   `ValueError`) — повідомлення з реченням помилки, фільтр робітника не змінюється,
   панель — `set_config` з попереднім конфігом (історія 30).
2. **«Save to config.yaml».** Порівняти сеансовий конфіг із файлом (`load_config(CONFIG_PATH)`)
   за набором `model.weights`, `model.imgsz`, `model.conf` (повзунок), `classes`,
   `display.center_line`, `display.color`; записати лише різницю через
   `core.config.save_values`. Рядок стану: «Saved: model.conf, classes» або «Nothing to
   save». `ConfigError`/`OSError` — повідомлення, файл не змінено.
3. **Межі тестами** (`tests/test_ui_boundaries.py`): жоден модуль `core/` не імпортує
   `PySide6` чи `ui` (аналіз імпортів через `ast` по файлах `core/`); у `ui/` і `app.py`
   немає кириличних символів.
4. **Офлайн-доказ** (`tests/test_offline_ui.py`) — підпроцес у стилі `tests/test_offline.py`
   (сокети в пастці, `QT_QPA_PLATFORM=offscreen`): справжня модель з `config.yaml`,
   `MainWindow`/робітник відкриває `data/test_images/bus.jpg`, чекає кадр, закривається.
   Жодної спроби мережі. Якщо ваг чи `bus.jpg` немає — `skip` з причиною, як наявні
   офлайн-тести.
5. **README** — розділ «Desktop app»: запуск `venv\Scripts\python app.py` (і `--source`),
   що в якому куті вікна, повзунок (нижня межа — `conf_debug`), налаштування діють одразу,
   «Save to config.yaml» пише лише змінене, файли в `out\` — як у `detect.py`, камера
   звільняється кнопкою «Stop» чи закриттям вікна. Англійською, у стилі наявного README.

## З брифа, дослівно

> «`ui/` imports `core/`, never the reverse.»
> «Fully offline at runtime. The network is used exactly twice in the whole project:
> `pip install`, and a one-time weight download. Never at inference time.»
> «Stop after each phase and show me what to run.»
> Доповнення: «кнопка «Save to config.yaml» записує змінені значення, коментарі у файлі
> лишаються»: «"а"»

## Розділи специфікації

Історії 28–35, 41–48; Рішення: «Налаштування — панель, не діалог», «Запис у
`config.yaml`»; Межі та шви — `ui/main_window.py`.

## Критерії приймання

- [ ] Вікно offscreen із заглушками: зміна в панелі → `worker.apply` з новим конфігом;
      `model_ready` заповнює класи; `model_failed` повертає стару модель у панелі
- [ ] «Save» на копії `config.yaml` у `tmp_path` (`CONFIG_PATH` підмінено): записано лише
      змінені ключі, решта файлу байт у байт; нічого не змінено — «Nothing to save»
- [ ] `test_ui_boundaries`: `core/` без Qt/`ui`; у `ui/` і `app.py` без кирилиці
- [ ] `test_offline_ui` проходить (або `skip` з причиною без ваг) — сокети не чіпались
- [ ] README має розділ «Desktop app», команди в ньому справжні
- [ ] Повний набір тестів зелений
