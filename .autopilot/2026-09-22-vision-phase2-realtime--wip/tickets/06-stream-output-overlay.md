# 06 — Вивід потоку і накладка цілі

**Вимоги:** R16i, R26, R27, R36i, R37, R38, R39, R50
**Blocked by:** 01
**Зона:** `core/output.py` · `core/draw.py` · `tests/test_output.py` · `tests/test_draw.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Модулі, що пишуть і малюють, уміють потік: JSONL із рядком на кадр, розмічене
`.mp4` для відеофайлу, рядок події в консоль, кадр події на диск, підсумок; на
накладці видно номер треку, ціль і рядок стану зверху. Фото пишуться і малюються
рівно як у фазі 1.

## З брифа, дослівно

> «Phase 1 output | OpenCV window + console lines + annotated JPG + JSON»
> «Do not skip `conf_debug`. Recording near-miss detections between 0.25 and 0.5 in the JSON is the main debugging tool for a missed object.»
> «actions (log line, save frame, call a function)»

Доповнення від користувача (про відео й вебкамеру): живе вікно; у консоль лише
події з `rules.yaml`; `out/<ім'я>.jsonl` — рядок на кадр, з near-miss і
`track_id`; для відеофайлу ще `out/<ім'я>_annotated.mp4`, для вебкамери відео не
пишеться — «Як ти запропонував».

## Розділи специфікації

Історії 18, 20, 35, 41–45; Рішення §14, §15; `interfaces.md` — форми `Event`, `TargetState`.

## Що зробити

**`core/output.py`** — лишається єдиним модулем `core/`, що друкує.

- `"track_id"` (int або `null`) з'являється **лише в JSONL**. `write_json` для фото
  пише рівно ту саму форму, що й зараз, без цього поля.
- `StreamWriter(source: str, cfg, fps: float, frame_size: tuple[int, int], video: bool)`
  — контекстний менеджер.
  - `write(frame, drawn, near_miss, target: TargetState | None, canvas)`:
    рядок у `out/<stem>.jsonl` (коли `output.save_json`):
    `{"source", "index", "time", "target", "detections": [... з "track_id" і "debug"]}`,
    `"target"` = `{"track_id", "locked", "lost"}` або `null` (коли немає цілі й
    блокування). `time` — 3 знаки після коми. Рядок пишеться і `flush`-иться
    одразу — обрив не втрачає записаного.
  - Кадр у `.mp4` (коли `video` і `output.save_image`): `cv2.VideoWriter`, кодек
    `mp4v`, `fps` потоку (при `fps <= 0` — константа модуля з коментарем), розмір
    — `frame_size`. `VideoWriter` на Windows іде вузьким рядком: писати в
    `out/.<ascii-ім'я>.part.mp4` і в `close()` — `Path.replace` на
    `out/<stem>_annotated.mp4`.
  - `close() -> list[Path]` — закриває все, повертає записані шляхи;
    ідемпотентний; викликається з `__exit__` і при винятку, щоб Ctrl+C лишав цілий
    `.mp4` і цілий JSONL.
  - Стем — наявний `_stem` (`camera:0` → `camera_0`).
- `print_event(event)` — один рядок:
  `[mm:ss.s] <rule>  <cls_name> #<track_id> <conf .2f>  dx <+d> dy <+d>`.
- `write_event_frame(event, source, index, image, cfg) -> Path` — у
  `<output.dir>/events/<stem>_<rule>_<index>.jpg` через `imencode` + байти.
  `index` — номер кадру (в `Event` його немає).
- `print_stream_summary(frames, events, paths)` — один рядок
  `N frames, M events, wrote a, b` (або `wrote nothing`).
- Друк фото (`print_console`) — без змін.

**`core/draw.py`**

- `annotate(image, detections, cfg, target: TargetState | None = None, status: str | None = None)`.
  Без нових аргументів — байт-у-байт той самий результат, що й зараз (фото).
- Мітка детекції з `track_id` — `#7 person 0.92` (колір, якщо є, як зараз).
- Ціль (`target.detection`): товща рамка іншого кольору, мітка `TARGET` над нею.
  Константи — у модулі, поруч з іншими кольорами.
- `status` — рядок угорі зліва з тим самим обведенням, що й інші тексти (його
  складає проводка: `target #7 person  dx +120 dy -40  ->  12.3 FPS` або
  `target: lost` / `target: none`).
- `aim` тут не викликається — рядок стрілки приходить у `status`.

**Тести.**

- `tests/test_output.py` (у `tmp_path`, `cfg` з `output.dir` у ньому):
  JSONL — рядок на кожен `write`, near-miss із `"debug": true`, `track_id`,
  форма `target`, `null` без цілі; `.mp4` існує після `close()`, `cv2.VideoCapture`
  читає з нього стільки ж кадрів (під ASCII-ім'ям); кириличний стем → файл із
  кириличним ім'ям існує; виняток усередині `with` усе одно лишає закриті файли;
  `save_json: false` → JSONL немає; `video=False` → `.mp4` немає; `print_event`
  формат (через `capsys`); `write_event_frame` пише у `events/`; `write_json` фото
  — без `track_id` (та сама форма, що й до таска).
- `tests/test_draw.py`: `annotate(img, dets, cfg)` і `annotate(img, dets, cfg,
  target=None, status=None)` дають однаковий масив; з `target` пікселі на рамці
  цілі відрізняються від виклику без `target`; зі `status` змінюється верхня
  смуга кадру; вхідний кадр не мутується; детекція з `track_id` малюється без
  помилки.

## Критерії приймання

- [ ] `out/<stem>.jsonl` — рядок на кадр, з `track_id`, `debug`, `target`
- [ ] `.mp4` відтворюється, кількість кадрів = кількість `write`; кириличний стем працює
- [ ] Виняток посеред запису лишає цілі файли
- [ ] Фото: JSON, JPG і консоль фази 1 — без змін форми
- [ ] Ціль видно на накладці; рядок стану зверху
- [ ] Нові тести зелені, уся суїта зелена
