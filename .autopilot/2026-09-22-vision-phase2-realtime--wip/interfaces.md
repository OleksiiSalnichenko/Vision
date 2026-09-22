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
