# 01 — Основа фази 2: контракт, конфіг, залежності, шина

**Вимоги:** R09, R13, R28, R32, R35i, R41, R49, R53
**Blocked by:** —
**Зона:** `core/types.py` · `core/config.py` · `config.yaml` · `core/events.py` · `requirements.txt` · `tests/conftest.py` · `tests/test_config.py` · `tests/test_events.py`
**Хвиля:** 1
**Status:** ready

## Що має запрацювати

Спільні примітиви, на які спираються всі інші таски фази 2, існують і перевірені:
`Detection` має `track_id`, `Frame` має `time`, `config.yaml` знає секції `tracker`
і `rules`, шина вміє викликати обробник за іменем, а у venv стоять два пакети, без
яких ByteTrack і OpenVINO не запускаються. Нічого з поведінки фази 1 не змінюється:
усі 34 наявні тести зелені без правок, окрім тих, що перевіряють схему конфігу.

## З брифа, дослівно

> «ByteTrack for stable `track_id` across frames.»
> «`Detection` is the only type that crosses module boundaries.»
> «Phase 2 layers rule evaluation and debouncing on top of this same bus without changing its signature.»
> «Every tunable number lives in `config.yaml`, never as a constant in code.»
> «The network is used exactly twice in the whole project: `pip install`, and a one-time weight download.»

## Розділи специфікації

Історії 10, 21, 36, 40a–40b, 47, 49; Рішення §3, §4, §13, §17, §18; `interfaces.md` — «Точні форми».

## Що зробити

- `core/types.py`: `Detection.track_id: int | None = None` (останнім полем, після
  `color`), `Frame.time: float = 0.0`. Контракт, без логіки. Оновити docstring
  модуля: він зараз каже «nothing is added here without changing that document
  first» — поля додані за рішенням специфікації фази 2, пропозиція змінити ARCH §7
  іде користувачу; напиши це одним реченням.
- `config.yaml` + `core/config.py`: секції `tracker` (`track_buffer` int > 0,
  `match_thresh` 0..1, `fuse_score` bool) і `rules` (`file` — непорожній текст), зі
  значеннями й коментарями з `interfaces.md`. Дата-класи, `_SECTIONS`, `_RULES`.
  Оновити шапку `config.yaml`, що перелічує ключі понад ARCH §9.
- `tests/conftest.py` / `tests/test_config.py`: спільна схема конфігу в тестах
  знає нові ключі; параметризований хвіст перевіряє, що `config.yaml` їх несе;
  хибний тип / діапазон нового ключа падає з іменем ключа.
- `core/events.py`: `call(name, detection)` — викликає зареєстровані обробники,
  чий `__name__ == name`, з тим самим фільтром класу, що й `emit` (обробник
  `@on_detect(cls="person")` не викликається для `cell phone`); падіння
  обробника логується й пропускається, як у `emit`. `names() -> set[str]` —
  імена всіх зареєстрованих обробників. `on_detect`, `emit`, `clear` — без змін
  сигнатур. Тести в `tests/test_events.py` (кожен кличе `clear()`).
- `requirements.txt`: додати `lap` і `openvino`. Встановити у venv:
  `venv\Scripts\python -m pip install -r requirements.txt`. Це дозволене звернення
  до мережі. Перевірити `venv\Scripts\python -c "import lap, openvino"`.
  Записати встановлені версії у звіт.

## Критерії приймання

- [ ] `Detection(...)` без `track_id` створюється як раніше; `Frame(...)` без `time` — теж
- [ ] `load_config("config.yaml")` повертає `cfg.tracker.track_buffer == 30`, `cfg.rules.file == "rules.yaml"`
- [ ] Відсутній `tracker.match_thresh` → `ConfigError` з іменем ключа; `match_thresh: 1.5` → `ConfigError`
- [ ] `events.call("greet", det)` викликає `greet`, не викликає інших; фільтр класу працює; `names()` містить `greet`
- [ ] `import lap, openvino` у venv працює; `requirements.txt` їх містить
- [ ] `venv\Scripts\python -m pytest -q` — усе зелене, нових тестів ≥ 5
