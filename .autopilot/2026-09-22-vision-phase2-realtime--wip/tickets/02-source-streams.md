# 02 — Відео і вебкамера в `Source`

**Вимоги:** R04, R05, R07, R08, R09, R41
**Blocked by:** 01
**Зона:** `core/source.py` · `scripts/grab.py` · `tests/test_source.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

`Source` приймає, крім фото й теки, відеофайл і вебкамеру, і видає ті самі
`Frame` із заповненими `index` і `time`. Усе нижче `Source` про тип входу не знає.
Фото й теки поводяться рівно як у фазі 1.

## З брифа, дослівно

> «Video and webcam branches in `Source`.»
> «One interface over a single image, a folder of images, a video file, a webcam index … Everything downstream is written against the iterator and does not know or care which is in use»
> «Default capture resolution is 1280x720, not 1080p»
> «`source: str  # file path, or "camera:0"`», «`index: int  # 0 for a still image, frame number for video`»

RTSP — **не робити** (користувач: «Відкласти»).

## Розділи специфікації

Історії 1–11; Рішення §2, §3; Межі: рядок `core/source.py`; Шов 4.

## Що зробити

- Розпізнавання специфікації входу:
  - наявна тека → тека фото (як зараз);
  - наявний файл із розширенням з `IMAGE_EXTENSIONS` → фото (як зараз);
  - наявний файл із розширенням з `VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v")` → відео;
  - `camera:N` або голе ціле число, яке **не** є наявним шляхом → камера N;
  - інше — як зараз (`source not found` / `not an image` — друге розширити до «not an image or video»).
- Відео: `cv2.VideoCapture`. На Windows `VideoCapture` іде вузьким рядком і не
  відкриває не-ANSI шлях — брати короткий 8.3-шлях через
  `ctypes.windll.kernel32.GetShortPathNameW`, лише коли шлях не кодується в
  системну кодову сторінку; якщо короткого імені немає (вимкнені на томі) —
  `ValueError("cannot open video: <path> (rename it to ASCII)")`. Файл, що не
  відкривається або не дає жодного кадру, — `ValueError("cannot open video: <path>")`
  **у конструкторі**, щоб `detect.py` показав одне речення і код 2.
  `index` — номер кадру з 0; `time` — `index / fps`, де `fps` із контейнера; при
  `fps <= 0` — `CAP_PROP_POS_MSEC / 1000`. Усі кадри, без пропусків. Реліз
  `VideoCapture` після останнього кадру і при передчасному закритті генератора
  (`try/finally` у `__iter__`).
- Камера: перенести `open_camera(index, cfg)` із `scripts/grab.py` у
  `core/source.py` без зміни поведінки (`CAP_DSHOW` на Windows, запит
  `capture.width/height`, `OSError` для відсутньої/зайнятої камери з текстом
  `camera N is not available or busy`); `grab.py` імпортує її звідти, його тести й
  поведінка не змінюються. Додатково для потоку: `CAP_PROP_BUFFERSIZE = 1`.
  Камеру відкривати в конструкторі `Source` (помилка — одразу, до моделі).
  `source` у кадрі — `camera:N`; `time` — `time.monotonic()` від першого кадру.
  Камера, що перестала віддавати кадри, — `__iter__` піднімає
  `OSError("camera N stopped delivering frames")`.
- Атрибути: `is_stream` (True для відео й камери), `fps` (контейнер для відео;
  `CAP_PROP_FPS` камери або 0, якщо вона не каже; 0 для фото), `frame_size`
  (`(w, h)` фактичний для потоку; `None` для фото/теки). `__len__`: фото/тека —
  як зараз; відео — кількість кадрів із контейнера; камера — 0 («невідомо»,
  сказати в docstring).
- Розмір кадру камери, що відрізняється від запитаного, — `log.warning` (логер
  модуля, не `print`).
- Модуль-docstring оновити: гілки фази 2 є, RTSP — ні.
- Тести `tests/test_source.py`: тест сам пише крихітне відео (`cv2.VideoWriter`,
  `mp4v`, 10 кадрів 64×48, fps 10) у `tmp_path` під ASCII-ім'ям і перейменовує в
  кириличне через `Path.replace` (бо `VideoWriter` теж вузький); перевіряє кількість
  кадрів, `index` 0..9, `time` зростає і дорівнює `index / fps`, `is_stream`,
  `frame_size`; кириличний шлях відкривається (тест пропускається з поясненням,
  якщо на томі немає коротких імен); неіснуючий `.mp4` → `FileNotFoundError`;
  битий `.mp4` (текст із розширенням) → `ValueError` з `cannot open video`;
  `camera:` без числа → `ValueError`. Камеру тести не відкривають.

## Критерії приймання

- [ ] Відео з `tmp_path` дає рівно 10 кадрів, `time` = `index / fps`
- [ ] Кириличне ім'я відео відкривається (або тест чесно пропущений з причиною)
- [ ] Битий/порожній відеофайл — `ValueError("cannot open video: …")` у конструкторі
- [ ] `Source("camera:0", cfg)` без камери → `OSError` з `camera 0 is not available or busy` (перевірити вручну, записати у звіт)
- [ ] `scripts/grab.py` працює як раніше, `open_camera` імпортується з `core.source`
- [ ] Фото й теки — без змін поведінки; уся наявна суїта зелена
