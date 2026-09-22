# Межі та контракти прогону — фаза 2

Цей файл читає кожен виконавець перед тим, як писати код. Спершу — `CLAUDE.md` у
корені: там наявний код фаз 0–1, його ключові файли, конвенції і пастки. Тут —
правила, межі фази 2, дослівно зі специфікації, і нижче те, що збудували таски.

## Правила проєкту

- **Мова коду, коментарів, логів, README і рядків інтерфейсу — англійська.**
  Без винятків. Українською — лише листування з користувачем.
- **Інтерпретатор — `venv\Scripts\python`** (3.11.9). Ніколи не голий `python`:
  системний 3.7.3 не чіпати.
- **Тести:** `venv\Scripts\python -m pytest -q`; один файл —
  `venv\Scripts\python -m pytest -q tests\test_x.py`. Зараз зелені 34.
- **Жодної мережі під час детекції**, на потоці, з трекером, з OpenVINO.
  Дозволено рівно два місця: `pip install` і `scripts/fetch_models.py`.
  Експорт в OpenVINO — офлайновий.
- **Інваріант офлайну.** `core/detector.py` виставляє `YOLO_OFFLINE=1` і
  `YOLO_AUTOINSTALL=0` на верхньому рівні, до будь-якого імпорту `ultralytics`;
  Ultralytics 8.4.157 читає `YOLO_OFFLINE` рівно раз — під час імпорту
  `ultralytics.utils`. Тому `ultralytics` імпортують **лише** `core/detector.py`,
  `core/tracker.py` і `scripts/export_openvino.py`, і два останні — **тільки
  після `import core.detector`** першим рядком своїх імпортів; сам
  `ultralytics` — ліниво, всередині функції чи `__init__`.
  `tests/test_offline.py` перевіряє це з підпроцесу — не переносити в основний.
- **Ніякого `cv2.imread` / `cv2.imwrite`.** Читати `np.fromfile` + `cv2.imdecode`,
  писати `cv2.imencode` + `Path.write_bytes`. `cv2.VideoCapture` і
  `cv2.VideoWriter` на Windows теж ідуть вузьким рядком — див. межі `source` і
  `output` нижче.
- **Жодного числа константою в коді, якщо користувач колись його покрутить.**
  Воно в `config.yaml` (або `rules.yaml`), дефолтів ніде немає: відсутній ключ —
  помилка з іменем ключа. Новий ключ = `config.yaml` + поле дата-класу + рядок
  у `_RULES` у `core/config.py`, разом. Презентаційні константи (кольори,
  товщини, шрифт, кодек, розширення файлів) — іменовані константи у своєму модулі.
- **`core/` не знає, як його запустили.** Ні `argparse`, ні `print` поза
  `core/output.py`. `core/` не імпортує з `ui/`.
- **Поділ drawn / near-miss робить тільки `detect.py`** через
  `core.detector.is_debug`. `draw.py`, `output.py`, `target.py`, `rules.py`
  порогів `conf` не знають — їм передають готові списки.
- **NMS не додається.** Абстракції навколо «вибору моделі» не будувати.
- **Конфіг не мутується:** перевизначення — через `dataclasses.replace`.
- **Помилка використання** (поганий шлях, поганий конфіг, немає ваг, камера
  зайнята) — одне речення в stderr і `EXIT_USAGE` (2), без трейсбеку.
- **Немає залежності — це `BLOCKED`, не привід ставити.** Виняток один: таск 01
  додає `lap` і `openvino` у `requirements.txt` і ставить їх у venv.
- **Не чіпати:** `ARCHITECTURE.md`, `PROJECT_PROMPT.md`, `docs/`, `.autopilot/`,
  `CLAUDE.md`.
- **Тести не вантажать модель і не йдуть у мережу.** `BYTETracker` — не модель.

## Межі, вирішені в специфікації

| Модуль | Володіє | Виставляє | Ховає |
|---|---|---|---|
| `core/types.py` | контракт даних | `Detection(…, color=None, track_id=None)`, `Frame(image, source, index, time=0.0)` | — |
| `core/source.py` | усі входи | `Source(spec, cfg)`: `__iter__() -> Iterator[Frame]`, `__len__()`, `is_stream: bool`, `fps: float` (0 для фото), `frame_size`; `open_camera(index, cfg) -> cv2.VideoCapture` (кидає `OSError`); `IMAGE_EXTENSIONS`, `VIDEO_EXTENSIONS` | короткий 8.3-шлях, бекенд камери, джерело часу |
| `core/detector.py` | інференс, офлайн-перемикачі | `Detector(cfg)`, `__call__(frame) -> list[Detection]`, `is_debug`, `MISSING_WEIGHTS_MESSAGE`, `MISSING_EXPORT_MESSAGE = "run scripts/export_openvino.py first"` | формат ваг, Ultralytics |
| `core/tracker.py` | ідентичність між кадрами | `Tracker(cfg)`, `update(frame, detections) -> list[Detection]`, `reset()` | `BYTETracker`, `Boxes`, відображення порогів |
| `core/target.py` | вибір цілі і блокування | `Targeting(cfg)`, `click(point, detections)`, `choose(detections, frame_size) -> TargetState`, `TargetState` | лічильник втрати |
| `core/rules.py` | `rules.yaml` і дебаунс | `load_rules(path) -> RuleSet`, `RulesError`, `RuleEngine(rule_set)`, `update(time, detections) -> list[Event]`, `Event`, `RuleSet.calls() -> set[str]` | стан треків, кулдауни, геометрія зон |
| `core/events.py` | шина обробників | `on_detect`, `emit`, `clear`, `call(name, detection)`, `names()` | реєстр |
| `core/output.py` | усе, що виходить назовні | наявне + `StreamWriter`, `print_event`, `write_event_frame`, `print_stream_summary` | імена файлів, JSONL, кодек, ASCII-перейменування |
| `core/draw.py` | накладка | `annotate(image, detections, cfg, target=None, status=None)` | кольори, шрифти |
| `detect.py` | проводка | `main`, `run_images`, `run_stream`, `Window`, `CONFIG_PATH`, `EXIT_USAGE`, `configure_console` | порядок кроків |
| `bench.py` | вимір | `--weights A [B …]` | — |
| `scripts/export_openvino.py` | одноразовий експорт | `main(argv=None) -> int` | виклик `YOLO.export` |

### Точні форми, про які таски домовляються між собою

Ці типи пишуть одні таски, а читають інші — паралельно. Форма фіксована тут:

```python
# core/types.py (таск 01)
@dataclass
class Detection:
    cls_id: int; cls_name: str; conf: float; bbox: tuple; center: tuple
    dx: int; dy: int; dx_pct: float; dy_pct: float
    color: str | None = None
    track_id: int | None = None      # set by core.tracker on streams only

@dataclass
class Frame:
    image: np.ndarray; source: str; index: int
    time: float = 0.0                # seconds since the stream started; 0 for stills

# core/target.py (таск 03)
@dataclass(frozen=True)
class TargetState:
    detection: Detection | None      # the target this frame, or None
    locked: bool                     # chosen by a click, not by distance
    lost: bool                       # locked, but its track is absent this frame

# core/rules.py (таск 04)
@dataclass(frozen=True)
class Event:
    rule: str                        # rule name from rules.yaml
    when: str                        # appeared | disappeared | present | entered
    detection: Detection             # the track's latest detection
    time: float                      # stream time the rule fired at
    actions: tuple                   # ("log",), ("save_frame",), ("call", "name") entries
```

`Event.actions` — кортеж елементів: рядок `"log"`, рядок `"save_frame"`, або
кортеж `("call", "<ім'я функції>")`.

Нові ключі `config.yaml` (таск 01):

```yaml
tracker:
  track_buffer: 30      # frames a lost track is kept before its id is retired
  match_thresh: 0.8     # IoU-based association threshold used by ByteTrack
  fuse_score: true      # blend detection score into the association cost

rules:
  file: rules.yaml      # conditions, actions and debouncing for streams
```

Форма `rules.yaml` (таск 04):

```yaml
debounce:
  confirm_frames: 3     # consecutive frames before a change counts
  cooldown: 5.0         # seconds a (rule, track) pair stays quiet after firing
zones:
  door: [0.0, 0.0, 0.3, 1.0]   # x1, y1, x2, y2 as fractions of the frame
rules:
  - name: person_appeared
    when: appeared      # appeared | disappeared | present | entered
    class: person       # optional; omitted means any class
    do: [log]
  - name: person_stays
    when: present
    seconds: 10         # required for present
    class: person
    do: [log, save_frame]
  - name: phone_at_door
    when: entered
    zone: door          # required for entered
    class: cell phone
    do: [log, {call: on_phone}]
```

**Шви для тестів** (жоден не вантажить модель і не йде в мережу):

1. `core/rules.py` — `RuleEngine.update` на синтетичних `Detection` з `track_id` і
   часом: кожна умова, дебаунс, кулдаун, мерехтіння; `load_rules` на хибних файлах.
2. `core/target.py` — `choose`/`click`: найближча, блокування, зняття, втрата.
3. `core/tracker.py` — `update` на синтетичних рамках, що рухаються: `track_id`
   стабільний, новий об'єкт — новий номер.
4. `core/source.py` — крихітне відео, записане тестом у `tmp_path` (у тому числі
   з кириличним ім'ям): кількість кадрів, зростання `time`, `is_stream`.
5. `tests/test_detect_cli.py` — `run_stream` зі `StubDetector` і штучним
   джерелом: JSONL має рядок на кадр, near-miss лише в JSONL.
6. `tests/test_offline.py` — третій підпроцес: імпорт `core.tracker`.

## Побудовано тасками

### З таска 01 — основа

- `Detection(..., color=None, track_id: int | None = None)`; `Frame(image, source, index, time: float = 0.0)`.
- `core.config.TrackerConfig(track_buffer, match_thresh, fuse_score)`, `RulesConfig(file)`;
  `Config.tracker`, `Config.rules`. У `config.yaml`: 30 / 0.8 / true / `rules.yaml`.
- `core.events.call(name, detection) -> None` — той самий фільтр класу, що й `emit`;
  обробник, що падає, логується і пропускається. `core.events.names() -> set[str]`.
  `on_detect` / `emit` / `clear` — без змін.
- `tests/conftest.CONFIG_SCHEMA` несе `tracker` і `rules` (45 / 0.7 / False /
  `"my_rules.yaml"`) — нові тести будують конфіг через неї, не пишуть свою схему.
- У venv: `lap 0.5.13`, `openvino 2026.4.0`, і разом із ним **`openvino-telemetry
  2025.2.0`** — див. таск 05.
- Тести: 52 зелені.

### З таска 02 — відео і вебкамера

- `Source(spec, cfg)`: `__iter__() -> Iterator[Frame]`, `__len__()` (0 для камери =
  «невідомо»), `is_stream: bool`, `fps: float`, `frame_size: tuple[int, int] | None`.
- `open_camera(index, cfg) -> cv2.VideoCapture` — тепер у `core.source`
  (`CAP_DSHOW`, буфер 1); `OSError("camera N is not available or busy")`.
  `scripts/grab.py` імпортує її звідти.
- `IMAGE_EXTENSIONS`, `VIDEO_EXTENSIONS`, `CAMERA_PREFIX = "camera:"`, `CAMERA_BACKEND`.
- Кадр камери: `source = "camera:N"`, `time` — монотонний від першого кадру. Камера
  замовкла посеред роботи → `__iter__` піднімає `OSError("camera N stopped delivering frames")`.
- Поганий `camera:` → `ValueError("not a camera index: …")`; битий відеофайл →
  `ValueError("cannot open video: …")` у конструкторі.
- Розмір кадру камери ≠ запитаному → `log.warning` у логері `core.source`: у stderr
  дійде, лише якщо `detect.py` налаштував `logging` (він налаштовує, рівень WARNING).
- Відеофайл відкривається двічі (конструктор — для ранньої помилки, `__iter__` —
  для читання), тож його можна ітерувати повторно. Камера лишається відкритою від
  конструктора до кінця єдиної ітерації.
- FFmpeg на битому `.mp4` сам друкує рядок у stderr («moov atom not found»);
  з процесу це не глушиться.

### З таска 03 — трекер і ціль

- `Tracker(cfg)`; `update(frame, detections) -> list[Detection]` — той самий
  порядок, `track_id` заповнений або `None`, вхідні не мутуються; `reset()`.
- **Новий об'єкт отримує `track_id` лише з другого кадру** (ByteTrack
  підтверджує на другій зустрічі після кадру 1): на першому — `None`. Накладка,
  JSONL і правила мусять тихо жити з `None`.
- Near-miss утримує наявний трек, але новий не починає.
- Лічильник id `STrack` у Ultralytics спільний на весь процес: новий `Tracker` або
  `reset()` перезапускає нумерацію для всіх — нормально, поки потік один.
- `TargetState(detection, locked, lost)` — frozen; `Targeting(cfg)`,
  `click(point, detections) -> None`, `choose(detections, frame_size) -> TargetState`
  (`frame_size` приймається, але відстань рахується з `dx`/`dy`).
- `tests/test_offline.py` має третій сценарій: імпорт і `update` трекера в чистому
  процесі не чіпають мережу.

### З таска 04 — правила

- `load_rules(path) -> RuleSet`; `FileNotFoundError("rules file not found: …")` або
  `RulesError(ValueError)` з текстом `rules[<name>].<key>: …` / `debounce.<key>: …` /
  `zones.<name>: …`.
- `RuleSet(confirm_frames, cooldown, zones: dict[str, (x1,y1,x2,y2)], rules: tuple[Rule, ...])`,
  frozen; `RuleSet.calls() -> set[str]`.
- `Rule(name, when, cls: str | None, seconds, zone, actions)` — ключ YAML `class`
  тут зветься `cls`.
- `Event(rule, when, detection, time, actions)` — рівно як вище; `RuleEngine(rule_set).update(time, detections) -> list[Event]`.
- Константи `CONDITIONS`, `SIMPLE_ACTIONS`, `CALL = "call"`.
- Модуль лише рахує: дії виконує `detect.py`. Попередження на старті «клас правила
  ніколи не збігається з класом обробника» (історія 40b) — за проводкою.
- `present`, придушений кулдауном, спрацює після нього (раз за перебування);
  придушені `appeared`/`entered` — губляться.
- **Кулдауни ключовані (правило, `track_id`) і не очищуються**, а новий `Tracker`
  починає id з 1 — тому **новий `RuleEngine` на кожен потік**, разом із новим `Tracker`.
- `Targeting` відпускає блокування через `tracker.track_buffer` кадрів — це
  збігається з ByteTrack лише тому, що `Tracker` не передає `frame_rate`. Не
  передавати fps у трекер без зміни `Targeting`.

### З таска 05 — OpenVINO (проміжно, таск продовжується)

- `core.detector.MISSING_EXPORT_MESSAGE = "run scripts/export_openvino.py first"`,
  `OPENVINO_SUFFIX = "_openvino_model"`; тека без `*.xml` — те саме повідомлення.
- **Телеметрія OpenVINO:** `import openvino` сам шле подію в Google Analytics
  (opt-out). `core/detector.py` ставить `sys.modules["openvino_telemetry"] = None`
  до будь-якого імпорту `openvino` — OpenVINO падає у власну no-op заглушку.
  Підпроцесний тест `tests/test_offline_openvino.py`. **Жоден модуль не імпортує
  `openvino` інакше, ніж після `core.detector`.**
- `scripts/export_openvino.py`: `main(argv=None) -> int`, `--weights`, `--force`;
  друк `exported: …` / `skip: …`.
- `bench.py --weights A [B …]`, `is_still(spec)`, `report_speedup(results)`,
  `STILLS_ONLY_MESSAGE`; відео й камера відхиляються **за шляхом, до `Source`**
  (інакше `"0"` відкриває справжню камеру — тест раз так і завис).
- Причина падіння 0xC0000005: `openvino` 2026.4.0 бачить iGPU цього ноутбука,
  Ultralytics бере пристрій AUTO і падає, компілюючи під GPU. **`openvino==2026.3.1`
  закріплено в `requirements.txt`** — ця версія GPU тут не бачить, інференс на CPU.
- `core/detector.py` ставить `KMP_BLOCKTIME=0` на верхньому рівні, до імпорту torch:
  без цього OpenMP-потоки torch тримають 4 ядра і OpenVINO стає повільнішим за `.pt`.
- Тека OpenVINO компілюється двічі на старті (Ultralytics друкує «Loading» двічі).
- `models/*_openvino_model/` у `.gitignore`.
- **Виміряно** (`bench.py`, `bus.jpg`, 3 прогріви + 10 проходів, openvino 2026.3.1):
  `.pt` 0.0791 с/кадр, 12.65 FPS; OpenVINO 0.0514 с/кадр, 19.45 FPS; прискорення
  1.54x (на 20 проходах 1.65x). Розкид окремих запусків ±30%: 4-ядерний U-процесор.
  На `bus.jpg` обидва формати дають ті самі 4 `person`, рамки розходяться ≤ 7 px.

### З таска 06 — вивід потоку і накладка

- `StreamWriter(source, cfg, fps, frame_size, video)` — контекстний менеджер;
  `write(frame, drawn, near_miss, target, canvas)`; `close() -> list[Path]`
  (ідемпотентний). Файли відкриваються на першому `write`: потік без кадрів — без
  файлів, підсумок «wrote nothing».
- Canvas іншого розміру, ніж `frame_size` → `ValueError` (а не мовчазна втрата кадру).
- JSONL: `{source, index, time, target: {track_id, locked, lost} | null, detections: [{track_id, …, debug}]}`;
  загублена заблокована ціль — `{"track_id": null, "locked": true, "lost": true}`.
- `print_event(event)` (читає `rule`, `time`, `detection`),
  `write_event_frame(event, source, index, image, cfg) -> Path`,
  `print_stream_summary(frames: int, events: int, paths)`.
- `annotate(image, detections, cfg, target=None, status=None)`.
- `.mp4` не пишеться, якщо сама `output.dir` має шлях поза кодовою сторінкою (`OSError`).

### З таска 07 — проводка

- `detect.run_images(source, detector, cfg, args, window) -> int` (фаза 1 без змін),
  `detect.run_stream(source, detector, cfg, args, window) -> int`.
- `Window(enabled, stream=False)`, `Window.on_click(callback((x, y)))`.
- `HANDLERS_PATH`, `EXIT_STREAM_FAILED = 1`; `--source` — «image, folder of images,
  video file, or camera:N».
- `handlers.py` у корені: `on_phone` з `@on_detect(cls="cell phone")`; імпортується,
  лише коли `rules.yaml` має `call`.
- ~~Попередження читає приватний `events._handlers`~~ — закрито таском 08.

### З таска 08 — камера звільняється завжди

- `Source.close()` (ідемпотентний), `with Source(...) as source:`, `Source.is_camera`.
  Повторна ітерація камери або після `close()` → `RuntimeError("source already consumed: camera N")`.
  Для відеофайлу `close()` нічого не робить: захоплення живе лише всередині ітерації.
- `core.source.is_stream_spec(spec) -> bool` — рішення за самим рядком, нічого не відкриває.
- `core.events.subscriptions(name) -> set[str | None]`; `detect.py` більше не читає `_handlers`.
- `detect.prepare_rules(cfg) -> RuleSet` — `rules.yaml` і `handlers.py` перевіряються
  **до** побудови `Source` (помилка правил не вмикає камеру).
- `detect.run_stream(..., rule_set=None)`; джерело відкривається в `with` у `main`,
  що покриває і завантаження моделі.
- Коди: збій читання кадру → 1; помилка запису файлу (кадр події, writer) → 2, одне речення.
- `sys.modules["openvino_telemetry"] = None` — пряме присвоєння.
- `tests/test_bench.py` підміняє `Source`/`open_camera` пасткою.

### З таска 09 — тести

- `conftest.schema_value(dotted)`, `conftest.config_text(overrides=None, without=())`,
  `write_config(overrides=None, without=())` — тести беруть значення з конфігу, не копіюють.
