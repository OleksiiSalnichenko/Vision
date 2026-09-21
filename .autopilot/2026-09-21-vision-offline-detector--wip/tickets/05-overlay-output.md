# 05 — Накладка, колір і вивід

**Вимоги:** R04, R19, R20, R21, R52, R53, R54, G01
**Blocked by:** 03
**Зона:** `core/draw.py`, `core/attributes.py`, `core/output.py`
**Хвиля:** 3
**Status:** ready

## Що має запрацювати

Те, що користувач бачить: кадр із накладкою, файли на диску і рядки в консолі.

Накладка — дослівно `ARCHITECTURE.md` §8: червоне перехрестя в центрі кадру,
рамка навколо кожного об'єкта, маленький зелений хрестик у центрі об'єкта,
`dx / dy` усередині рамки. Плюс `display.center_line` (типово `false`) — лінія
від центру кадру до центру об'єкта. Підписи вимикаються
`display.show_labels: false`.

`dominant_color(image, bbox)` — KMeans зі `scikit-learn` по **центральній
третині** рамки (країв рамки завжди торкається фон), назва з невеликої
палітри. Модуль викликається тільки коли увімкнений `--color`.

Вивід: `out\<stem>_annotated.jpg`, `out\<stem>.json`, по рядку на детекцію в
консоль. Повторний запуск перезаписує — це інструмент налагодження, не архів.
JSON містить усі детекції, включно з тими, що між `conf_debug` і `conf`, з
позначкою.

Ці модулі не знають, звідки їх викликали: жодного `argparse`, жодного читання
CLI. Друк — тільки в `output.py`.

## З брифа, дослівно

> «Phase 1 output | OpenCV window + console lines + annotated JPG + JSON»
> «A crosshair marks the frame centre, a dot marks each object's centre, and a
> line joins them.»
> «Colour attribute | in phase 1, but behind a `--color` flag, in its own
> module»
> «Code, comments, logs, README, UI strings | **all English**»

З `ARCHITECTURE.md` §8 (нормативне джерело):

> «No line is drawn between the two centres ... Labels can be switched off»

З доповнення брифа (2026-09-21):

> «Прапорець у config.yaml, типово вимкнено»

## Розділи специфікації

Історії 10, 12, 13, 16, 19; Рішення §колір, §вивід, §config.yaml.

## Критерії приймання

- [ ] `annotate` малює перехрестя, рамки, зелений хрестик і `dx / dy` усередині рамки
- [ ] `display.center_line: true` додає лінію; типово її немає
- [ ] `display.show_labels: false` прибирає підписи, рамки лишаються
- [ ] `dominant_color` працює по центральній третині рамки і повертає назву з палітри
- [ ] `write_json` пише всі детекції, включно з `debug`, і позначає їх
- [ ] `write_image` пише `out\<stem>_annotated.jpg`; тека створюється, якщо її немає
- [ ] `print_console` — по рядку на детекцію, англійською
- [ ] Порожній список детекцій дає коректний JSON з порожнім масивом і кадр із самим перехрестям
- [ ] У цих модулях немає ні `argparse`, ні імпортів з `ui`
