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
