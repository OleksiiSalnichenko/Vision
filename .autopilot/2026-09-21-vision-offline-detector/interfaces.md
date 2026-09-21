# Межі та контракти прогону

Цей файл читає кожен виконавець перед тим, як писати код. Перша половина —
правила проєкту; друга — межі, вирішені в специфікації, дослівно. Нижче
дописується те, що збудували завершені таски.

## Правила проєкту

- **Мова коду, коментарів, логів, README і рядків інтерфейсу — англійська.**
  Без винятків. Українською ведеться тільки листування з користувачем.
- **Стек:** Python 3.11 (venv у `venv\` всередині проєкту), `ultralytics>=8.4`,
  `opencv-python`, `pyyaml`, `numpy`, `scikit-learn`, `pytest`.
- **Запуск:** `venv\Scripts\python detect.py --source <шлях>`
- **Тести:** `venv\Scripts\python -m pytest -q`
- **Жодної мережі в коді, що виконується під час детекції.** Мережа дозволена
  рівно в двох місцях: `pip install` і `scripts/fetch_models.py`. Усе інше, що
  хоче в мережу, — помилка, а не зручність.
- **Ваги вантажаться за явним шляхом із `config.yaml`.** `Detector.__init__`
  піднімає `FileNotFoundError: run scripts/fetch_models.py first`, якщо файлу
  немає. Мережевого фолбеку немає ніде.
- **`core/` не імпортує нічого з `ui/` і не знає, як його запустили.** Ні
  `argparse`, ні `print` у модулях ядра: CLI живе в `detect.py`, друк — у
  `core/output.py`.
- **NMS не додається.** YOLO26 закриває дублікати всередині моделі.
- **Жодного числа константою в коді.** Усе, що крутиться, живе в `config.yaml`.
- **Абстракції навколо «вибору моделі» не будувати.** Перехід `n` → `s` — це
  правка одного рядка конфігу.
- **`core/detector.py` — єдиний модуль проєкту, що імпортує `ultralytics`.**
  Це межа, а не збіг: він виставляє `YOLO_OFFLINE` і `YOLO_AUTOINSTALL=0` на
  верхньому рівні, **до** імпорту ultralytics, а Ultralytics 8.4.157 читає
  `YOLO_OFFLINE` рівно один раз — під час імпорту `ultralytics.utils`
  (`ONLINE = is_online()`). Будь-який інший модуль, що імпортує ultralytics
  раніше, тихо знеструмить вимкнення телеметрії і поверне вихідні запити на
  інференсі. Виняток один: `scripts/fetch_models.py` — він поза цим шляхом
  імпорту і лишається онлайновим навмисно.
- **Немає залежності — це `BLOCKED`, а не привід її поставити.** Повертай
  таск із поясненням, нічого не встановлюй.
- **Не чіпати:** `ARCHITECTURE.md`, `PROJECT_PROMPT.md`, `docs/`, `.autopilot/`.

## Межі, вирішені в специфікації

| Модуль | Володіє | Виставляє | Ховає |
|---|---|---|---|
| `core/__init__.py` | тим, що `core` — пакет | нічого (порожній, крім рядка версії) | — |
| `core/types.py` | формою даних, що перетинають межі | `Detection`, `Frame` (поля — ARCH §7) | — (це контракт, а не логіка) |
| `core/config.py` | читанням і валідацією `config.yaml` | `load_config(path) -> Config` | схему за замовчуванням, перевірки типів і діапазонів |
| `core/source.py` | перетворенням входу на кадри | `Source(spec, cfg)` з `__iter__() -> Iterator[Frame]` | розбір «файл це чи тека», порядок обходу, читання з диска |
| `core/detector.py` | інференсом і фільтрами | `Detector(cfg)`, `__call__(frame) -> list[Detection]` | завантаження ваг, letterbox, два пороги, білий список класів |
| `core/geometry.py` | арифметикою зміщень | `offsets(bbox, frame_size) -> (center, dx, dy, dx_pct, dy_pct)` | — (чиста функція) |
| `core/attributes.py` | домінуючим кольором | `dominant_color(image, bbox) -> str` | кластеризацію і палітру назв |
| `core/draw.py` | накладкою | `annotate(image, detections, cfg) -> image` | кольори, товщини, розкладку підписів |
| `core/events.py` | шиною подій | `on_detect(cls=None)`, `emit(detection)` | реєстр підписників |
| `core/output.py` | видачею назовні | `write_json(...)`, `write_image(...)`, `print_console(...)` | формат JSON, імена файлів, формат рядка |
| `core/aim.py` | заглушкою наведення | `aim(dx, dy)` | те, що поки нічого не робить, крім стрілки |
| `detect.py` | CLI фази 1 | `detect.py --source ... [--color] [--conf] [--classes] [--no-window]` | порядок виклику модулів |
| `bench.py` | вимірюванням | `bench.py --source ... [--runs N]` | прогрів, усереднення |
| `scripts/fetch_models.py` | одноразовим онлайн-кроком | команда без аргументів | URL, `.part`, SHA256 |
| `scripts/grab.py` | кадрами з камери | `grab.py [--camera 0] [--count N]` | роботу з `cv2.VideoCapture` |

**Шви для тестів — три, і більше не потрібно:**

1. `core/geometry.offsets` — чиста арифметика, перевіряється значеннями.
2. `core/config.load_config` — валідний конфіг завантажується, зламаний падає з
   назвою ключа.
3. `core/detector.Detector.__init__` — без файлу ваг піднімає `FileNotFoundError`
   з точним текстом.

Малювання, JSON і камера автоматично не тестуються: їх приймання — оком.

## Побудовано тасками

### З таска 01 — середовище

- Інтерпретатор проєкту — `venv\Scripts\python` (Python 3.11.9). Системний
  `python` лишається 3.7.3 і не використовується ніде.
- `py -3.11` працює; `py -0p` друкує нову версію як `-3.1-64` — косметичний баг
  старого лаунчера від 3.7, шлях у виводі правильний.
- Тести: `venv\Scripts\python -m pytest -q`; один файл —
  `venv\Scripts\python -m pytest -q <шлях>`.
- `requirements.txt`: `ultralytics>=8.4`, `opencv-python`, `pyyaml`, `numpy`,
  `scikit-learn`, `pytest` — без верхніх меж.
- Встановлено: ultralytics 8.4.157, torch 2.14.0+cpu, opencv-python 5.0.0.93,
  numpy 2.4.6, scikit-learn 1.9.1, pyyaml 6.0.3, pytest 9.1.1.
- `torch.cuda.is_available()` → `False`. Це очікувано і не помилка: колеса CPU.

### З таска 02 — ваги і тестове фото

- `venv\Scripts\python scripts\fetch_models.py` — без аргументів, exit 0 / 1.
  Єдине місце в проєкті, де код іде в мережу. Ніде більше мережі бути не повинно.
- На диску: `models\yolo26n.pt`, `models\yolo26s.pt`, `data\test_images\bus.jpg`.
- `models\checksums.txt` — рядки `<sha256>  <шлях від кореня проєкту>`, три файли.
- Статуси в підсумку скрипта: `downloaded` | `skip`.
- Стейджинг завантаження — тека `models\.part\<ім'я>.pt` (резолвер Ultralytics
  шукає ассет за точним іменем). Недописаного файлу в `models\` не буває.
- Пороги розміру — іменовані константи всередині скрипта, не в `config.yaml`:
  це одноразовий інструмент, а не модуль ядра.

### З таска 03 — ядро: типи, конфіг, геометрія

- `core.types.Detection(cls_id:int, cls_name:str, conf:float, bbox:tuple,
  center:tuple, dx:int, dy:int, dx_pct:float, dy_pct:float, color:str|None=None)`
- `core.types.Frame(image:np.ndarray, source:str, index:int)`
- `core.geometry.offsets(bbox:(x1,y1,x2,y2), frame_size:(width,height))
  -> (center:(int,int), dx:int, dy:int, dx_pct:float, dy_pct:float)`.
  Центр і `dx`/`dy` округлені до цілих пікселів; `dx_pct` рахується з цілого `dx`.
- `core.config.load_config(path) -> Config`; `core.config.ConfigError(ValueError)`
- `Config`: `.model(.weights,.imgsz,.conf,.conf_debug)`, `.classes:list[str]`,
  `.display(.show_labels,.show_offsets,.crosshair,.center_line)`,
  `.output(.save_json,.save_image,.dir)`, `.capture(.width,.height)`
- **Дефолтів у коді немає взагалі.** Відсутній ключ — `ConfigError` з іменем
  ключа. Новий ключ додається в `config.yaml`, а не константою в модулі.
- `tests/conftest.py` додає корінь проєкту в `sys.path` — інакше `import core`
  не працює без встановлення пакета.
- Не винаходь заново: геометрію рахує `offsets`, конфіг читає `load_config`.

### З таска 04 — джерело, детектор, події, наведення

- `core.source.Source(spec: str|Path, cfg: Config)`; `__iter__() -> Iterator[Frame]`,
  `__len__() -> int`; `core.source.IMAGE_EXTENSIONS: tuple[str, ...]`.
  Порядок обходу теки — за іменем, регістронезалежно.
- `core.detector.Detector(cfg: Config)`; `__call__(frame: Frame) -> list[Detection]`.
  Повертає **все від `conf_debug` і вище**, відсортоване за `conf` спадно.
- `core.detector.is_debug(detection: Detection, cfg: Config) -> bool` — **ось як
  відрізнити near-miss**. Мітки `debug` у самому `Detection` немає (поле з ARCH §7
  не додавалося). **Поділ робить викликач — `detect.py`**, і тільки він: він кличе
  `is_debug` один раз, малює і друкує те, що вище `conf`, а в `write_json` передає
  решту окремим аргументом `debug_detections`. `draw.py` і `output.py` порогів не
  знають і `is_debug` не викликають.
- `core.detector.MISSING_WEIGHTS_MESSAGE: str` — текст `FileNotFoundError`.
- `core.events.on_detect(cls: str|None = None)`; `core.events.emit(detection)`;
  `core.events.clear()`; `Handler = Callable[[Detection], None]`.
  Автоматичного скидання між тестами немає: хто пише тести на `on_detect`,
  кличе `clear()` сам.
- `core.aim.aim(dx: int, dy: int) -> str` — заглушка. Параметра кадру в контракті
  немає, тому повертає рядок-стрілку (ASCII: консоль Windows у cp1251).
  Малювання стрілки на кадрі — за `core/draw.py`, якщо знадобиться.
- Шлях до ваг резолвиться **відносно поточної теки**. Запуск не з кореня проєкту
  вимагає абсолютного шляху в `config.yaml`.

### З таска 05 — накладка, колір, вивід

- `core.draw.annotate(image, detections: Sequence[Detection], cfg) -> np.ndarray`
  — повертає копію, вхідний кадр не мутується. Центр кадру бере з
  `geometry.offsets((0,0,w,h),(w,h))` — одне джерело з `dx`/`dy`, щоб перехрестя
  і нуль зміщення збігалися на непарних сторонах.
- Запис зображення йде через `cv2.imencode` + байти на диск, не `cv2.imwrite`:
  на Windows `imwrite`/`imread` проходять через вузький рядок кодової сторінки і
  мовчки не працюють на кириличному шляху. Читання в `source.py` обходить це
  через `np.fromfile` + `imdecode`. **Нового коду з `cv2.imwrite`/`cv2.imread`
  у проєкті бути не повинно.**
- `core.attributes.dominant_color(image, bbox) -> str`. Палітра: red, orange,
  yellow, green, cyan, blue, purple, pink, brown, black, gray, white.
  `ValueError` на порожньому або виродженому bbox.
- `core.output.write_json(source, detections, cfg, debug_detections=()) -> Path|None`
- `core.output.write_image(source, image, cfg) -> Path | None`
- `core.output.print_console(source, detections) -> None`
- **Поділ на `detections` і `debug_detections` робить викликач** (`detect.py`):
  ці модулі порогів не знають. Розділяти через `core.detector.is_debug`.
  Малюються і друкуються тільки перші; у JSON ідуть обидва, near-miss з `"debug": true`.
- JSON: `{"source": str, "detections": [{cls_id, cls_name, conf, bbox[4],
  center[2], dx, dy, dx_pct, dy_pct, color, debug}]}` — один масив.
- Консоль: `<stem>: N detections`, далі по рядку на детекцію.
- Імена файлів: `<output.dir>\<stem>.json`, `<output.dir>\<stem>_annotated.jpg`;
  тека створюється; перезапис; `camera:0` → stem `camera_0`.
- `write_json` / `write_image` самі шанують `output.save_json` / `output.save_image`
  і повертають `None`, коли прапорець вимкнено.
- Кольори, товщини, шрифт, розкладка підписів, `k` для KMeans і палітра назв —
  іменовані константи всередині цих модулів: таблиця «Межі та шви» віддала їх
  цим модулям у володіння. Це не тюнабли `config.yaml`.

### З таска 06 — CLI, вимірювання, кадри з камери, README

- `detect.py`: `main(argv=None) -> int`, `parse_args`, `configure_console`,
  `with_overrides(cfg, args) -> Config`, `process(frame, detector, cfg, want_color)`,
  `CONFIG_PATH: Path`, `EXIT_USAGE = 2`, `Window(enabled).show(image) -> bool`.
- `bench.py`: `main(argv=None) -> int`, `one_pass`, `measure`, `report`.
- `scripts/grab.py`: `main(argv=None) -> int`, `open_camera` (`OSError`, якщо
  камера зайнята або відсутня), `grab`, `IMAGES_DIR`.
- **Поділ на drawn / near-miss живе тільки в `detect.py`** — він єдиний викликач
  `core.detector.is_debug`.
- `--conf` нижче `conf_debug` опускає і `conf_debug`: інакше інференс іде з
  підлогою 0.25 і прапорець мовчки нічого не змінює.
- Нові ключі конфігу: `capture.camera`, `capture.count`, `capture.interval`,
  секція `bench` (`runs`, `warmup`). Схема `config.yaml` тепер ширша за ARCH §9.
- `bench.py` і `scripts/grab.py` імпортують `configure_console`, `CONFIG_PATH`,
  `EXIT_USAGE` з `detect.py` — щоб пастка cp1252 була закрита в одному місці.
