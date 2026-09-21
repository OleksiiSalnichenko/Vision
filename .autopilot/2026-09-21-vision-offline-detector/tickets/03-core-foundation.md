# 03 — Ядро: типи, конфіг, геометрія

**Вимоги:** R17, R18, R21, R43, R48, R50, R55, R56, G01, G02
**Blocked by:** 01
**Зона:** `core/__init__.py`, `core/types.py`, `core/config.py`, `core/geometry.py`, `config.yaml`, `tests/`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Фундамент, на який спираються всі інші таски: форма даних, читання конфігу і
арифметика зміщень. Плюс `pytest`, зелений на двох із трьох швів.

`Detection` і `Frame` — дослівно поля з `ARCHITECTURE.md` §7, без додавань:

```python
@dataclass
class Detection:
    cls_id: int
    cls_name: str
    conf: float
    bbox: tuple          # (x1, y1, x2, y2) у пікселях вихідного зображення
    center: tuple        # (cx, cy)
    dx: int              # cx - frame_center_x, праворуч додатне
    dy: int              # cy - frame_center_y, вниз додатне
    dx_pct: float        # dx / (width/2), -1..1
    dy_pct: float        # dy / (height/2), -1..1
    color: str | None    # тільки коли заданий --color

@dataclass
class Frame:
    image: np.ndarray    # BGR, як повертає OpenCV
    source: str          # шлях до файлу або "camera:0"
    index: int           # 0 для нерухомого зображення
```

`config.yaml` — схема з `ARCHITECTURE.md` §9 плюс один ключ
`display.center_line: false`. Валідація при завантаженні: невідомий ключ —
попередження в лог, некоректний тип або діапазон — падіння з назвою ключа.

## З брифа, дослівно

> «The structure, module contracts, data flow and config schema are specified in
> sections 6 to 9 of `ARCHITECTURE.md`. Follow them.»
> «whitelist in `config.yaml`, not all 80 COCO classes»
> «`imgsz: 640` (the model's native training size)»

З доповнення брифа (2026-09-21):

> лінія між центрами: «Прапорець у config.yaml, типово вимкнено»
> тести: «Мінімальний pytest»

## Розділи специфікації

Історії 11, 26, 27; Рішення §геометрія, §config.yaml; Межі та шви §1–2.

## Критерії приймання

- [ ] `core/types.py` містить `Detection` і `Frame` з полями рівно як вище
- [ ] `config.yaml` містить усі ключі з ARCH §9 плюс `display.center_line: false`
- [ ] `load_config` на валідному конфігу повертає об'єкт з усіма значеннями
- [ ] `load_config` на некоректному типі або діапазоні падає, і в тексті помилки є назва ключа
- [ ] `offsets` рахує `dx`, `dy` у пікселях і `dx_pct`, `dy_pct` у −1..1; праворуч і вниз додатні
- [ ] `pytest -q` зелений: geometry (значеннями, зокрема центр кадру → 0,0) і config (валідний + зламаний)
- [ ] Жодного порогу, розміру чи шляху константою в коді
