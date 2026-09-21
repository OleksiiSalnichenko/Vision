# 04 — Детекція: джерело, детектор, події, наведення

**Вимоги:** R02, R03, R08, R10, R16, R26, R28, R29, R30, R31, R32, R49, R51, G02
**Blocked by:** 02, 03
**Зона:** `core/source.py`, `core/detector.py`, `core/events.py`, `core/aim.py`, `tests/test_detector.py`
**Хвиля:** 3
**Status:** ready

## Що має запрацювати

Шлях від файлу на диску до списку `Detection`. Після цього таска в Python-сесії
можна зробити: створити `Source` на фото, прогнати через `Detector` і отримати
об'єкти з класами, впевненістю і порахованими зміщеннями.

`Source` — один інтерфейс над усіма входами, у цій фазі реалізовані два:
одне зображення і тека з зображеннями. Відео, вебка і RTSP — фаза 2; інтерфейс
має бути таким, щоб їх додавання не чіпало нічого нижче за течією.

`Detector` вантажить ваги **за явним шляхом із конфігу**. До будь-якого дотику
до `YOLO(...)` перевіряє, що файл існує, і якщо ні — піднімає
`FileNotFoundError: run scripts/fetch_models.py first`. Мережевого фолбеку
немає. Це пастка №1 з брифа.

Один прохід інференсу з `conf=conf_debug` (0.25), далі поділ: `>= conf` (0.5) —
«справжні» детекції; решта — позначені `debug` і йдуть тільки в JSON. Два
запуски моделі коштують удвічі, а дають те саме.

NMS не додавати. YOLO26 закриває дублікати всередині.

`events.on_detect(cls=...)` — синхронний виклик, по разу на детекцію, без
правил і дебаунсу. `aim(dx, dy)` — заглушка, що малює стрілку.

## З брифа, дослівно

> «`config.yaml` stores an explicit path (`models/yolo26n.pt`), and
> `Detector.__init__` must raise
> `FileNotFoundError: run scripts/fetch_models.py first` when the file is
> missing. It must never fall back to the network.»
> «**YOLO26 is NMS-free.** ... Do not add one; do not port NMS code from YOLO11
> examples.»
> «Do not skip `conf_debug`. Recording near-miss detections between 0.25 and 0.5
> in the JSON is the main debugging tool for a missed object.»
> «**`core/` must not import from `ui/`** or know how it was launched.»
> «Switching is one config line. Do not build abstraction around "model
> selection".»

## Розділи специфікації

Історії 14, 15, 17, 20, 21, 22; Рішення §Detector, §розмір моделі, §NMS,
§два пороги, §геометрія; Межі та шви §3.

## Критерії приймання

- [ ] `Source` на файлі дає один `Frame`; на теці — по кадру на зображення, у стабільному порядку
- [ ] `Detector(cfg)` без файлу ваг піднімає `FileNotFoundError` з текстом `run scripts/fetch_models.py first`
- [ ] `Detector` на `bus.jpg` повертає непорожній список `Detection` з коректними `dx`, `dy`, `dx_pct`, `dy_pct`
- [ ] Детекції між `conf_debug` і `conf` присутні в результаті з позначкою, а не відкинуті
- [ ] Білий список класів з конфігу застосовується; порожній список означає всі
- [ ] `@on_detect(cls="person")` викликається по разу на кожну відповідну детекцію
- [ ] `aim(dx, dy)` існує і малює стрілку, нічого більше
- [ ] `grep` по `core/` не знаходить ні `argparse`, ні `print`, ні імпортів з `ui`
- [ ] `pytest -q` зелений, зокрема шов №3 (відсутні ваги)
