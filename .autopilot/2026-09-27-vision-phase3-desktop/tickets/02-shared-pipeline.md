# 02 — Спільний конвеєр кадру: `core/pipeline.py`, `detect.py` над ним

**Вимоги:** R21, R02, R32, R15i, R15i.2, R15i.3, R19i, R25, R26, R29, R33
**Blocked by:** 01
**Зона:** `core/pipeline.py` · `detect.py` · `tests/test_pipeline.py` · `tests/test_detect_cli.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Порядок кадру (детекція → трекінг → поділ `is_debug` → колір → ціль → рядок стану →
накладка → правила → дії → запис) переїжджає з `detect.py` у новий `core/pipeline.py`,
щоб застосунок (таски 03–06) і CLI ганяли **один і той самий** конвеєр. `detect.py`
стає тонким: прапорці, друк у консоль, коди виходу. **Поведінка `detect.py` не
змінюється** — ні вивід у консоль, ні файли, ні коди виходу.

Контракт `core/pipeline.py` — у `interfaces.md`, рядок `core/pipeline.py`. Головне:

- Модуль нічого не друкує і не знає Qt. Дія `log` правила — колбек `on_log(event)` від
  викликача (`detect.py` передає `output.print_event`). `save_frame` і `call` виконуються
  всередині однаково для обох запусків.
- `core/pipeline.py` — єдиний викликач `is_debug`. `detect.py` більше його не викликає.
- `StreamSession` — контекстний менеджер, файли (`StreamWriter`) відкриваються на першому
  `step`, `close()` ідемпотентний і повертає шляхи. `retune(cfg, want_color)` міняє поріг
  (через `Tracker.set_conf` з таска 01), дисплей і колір на наступний кадр без скидання
  треків; `set_detector(detector)` підміняє модель між кадрами.
- `StillResult.detections` — усі детекції від `conf_debug`, щоб `resplit_still` міг
  перерозділити їх під новий поріг без моделі.
- Виклики `output.*` і `events.*` — через атрибут модуля (тести підміняють
  `detect.output.write_event_frame`; це той самий об'єкт модуля `core.output`).
- `detect.prepare_rules(cfg)` лишається як обгортка й читає `detect.HANDLERS_PATH` у
  момент виклику (тести його підміняють).
- Колір у CLI: `want_color = args.color or cfg.display.color`.

`detect.py` зберігає всі публічні імена, які перелічені в `CLAUDE.md` «Key files»
(`process`, `run_images`, `run_stream`, `Window`, `configure_console`, `CONFIG_PATH`,
`HANDLERS_PATH`, `PROJECT_ROOT`, `EXIT_*`, …) — `bench.py` і скрипти їх імпортують.

## З брифа, дослівно

> «| 3 — app | `ui/` (PySide6, imports `core/` as a library) | nothing |»
> «`core/` must never import from `ui/` or know how it was launched.»
> «Do not skip `conf_debug`. Recording near-miss detections between 0.25 and 0.5 in the
> JSON is the main debugging tool for a missed object.»
> «If something in `ARCHITECTURE.md` turns out to be wrong once code exists, say so and
> propose the change rather than quietly working around it.»

## Розділи специфікації

Рішення: «Один конвеєр на два запуски», «Поріг на потоці», «Колір як ключ конфігу»;
Межі та шви — рядки `core/pipeline.py`, `detect.py`; шов 1; Пропозиції до ARCHITECTURE.md.

## Критерії приймання

- [ ] Усі наявні тести проходять. Тест у `test_detect_cli.py` міняється лише там, де
      підміняв ім'я, яке переїхало, — і твердження лишається те саме
- [ ] `tests/test_pipeline.py` зі `StubDetector`: фото — поділ на намальовані / near-miss,
      `resplit_still` під інший поріг дає інший поділ без виклику детектора; `save_still`
      пише ті самі `.json`/`_annotated.jpg`, що `detect.process`
- [ ] Потік: `step` повертає `StreamResult` з подіями; `log` іде в `on_log`, а не в stdout;
      `save_frame` пише кадр події; `close()` двічі — без помилки, повертає шляхи
- [ ] `retune` з нижчим порогом: наступний кадр малює об'єкт, який раніше був near-miss, і
      він отримує `track_id`; id наявних треків не змінились
- [ ] `set_detector` між кадрами: наступний `step` кличе новий детектор, трекер не скинуто
- [ ] `detect.py --color` і `display.color: true` малюють колір; `display.color: false` без
      прапорця — ні (тест на `want_color`)
- [ ] `grep is_debug` — лише `core/detector.py` (визначення) і `core/pipeline.py`
- [ ] `core/pipeline.py` не імпортує `PySide6`/`ui` і не має `print`
