# 04 — Головне вікно: джерела, живий перегляд, список об'єктів, повзунок, події

**Вимоги:** R04, R05, R05.1, R05.3, R06, R06.1, R06.2, R07, R07.1, R09, R09.1, R09.2, R10, R10.4, R12i, R12i.1, R12i.2, R14i, R15i, R15i.1, R15i.2, R17i, R18i, R23, R26, A01
**Blocked by:** 03
**Зона:** `ui/view.py` · `ui/main_window.py` · `app.py` · `tests/test_ui_window.py` · `tests/test_ui_view.py`
**Хвиля:** 4
**Status:** ready

## Що має запрацювати

Користувач запускає `venv\Scripts\python app.py` і отримує вікно `Vision`, де все з
фаз 1–2 робиться кнопками. Панель налаштувань (таск 05) у цьому таску ще **не**
вбудовується — лише місце для неї (правий бік), інтеграція — таск 06.

- **`app.py`** у корені: `main(argv=None) -> int`, необов'язковий `--source <spec>` (той
  самий формат, що в `detect.py`), `configure_console()` і `CONFIG_PATH` з `detect.py`;
  битий `config.yaml` — одне речення в stderr і `EXIT_USAGE`, вікно не відкривається.
- **Старт**: робітник у `QThread`, `load_model()`; поки вантажиться — «Loading model…» і
  неактивні кнопки відкриття; помилка моделі — `QMessageBox.warning` з реченням, кнопки
  лишаються неактивні. Порожній стан перегляду: «Open a photo, a folder, a video or a
  camera»; порожня таблиця: «No objects».
- **Джерела**: «Open file…» (фото або відео — фільтр з `IMAGE_EXTENSIONS` і
  `VIDEO_EXTENSIONS` у `core.source`), «Open folder…», номер камери (спінбокс, старт —
  `capture.camera`) + «Open camera», «Stop», «Pause»/«Resume» (лише відеофайл, також
  пробіл), для теки — «◀ Prev» / «Next ▶» і «i / N».
- **`ui/view.py`**: `FrameView` показує `canvas` (BGR → RGB, `QImage` з копією буфера),
  вписаний зі збереженням пропорцій; лівий клік → сигнал `clicked(x, y)` у пікселях кадру
  через чисту функцію `to_image_point(widget_point, widget_size, image_size)` (`None` —
  клік у поле поза кадром). Клік іде в `worker.click` лише на потоці.
- **Таблиця об'єктів**: `#id`, class, conf, dx, dy, dx %, dy %, colour (колонка colour
  видима, лише коли колір увімкнено); рядок цілі виділений і позначений `TARGET`; під
  таблицею — «N near-miss below threshold (in the files only)».
- **Повзунок «Confidence»**: крок 0.01, від `model.conf_debug` до 1.00, старт `model.conf`,
  значення поруч («0.50»), підказка про нижню межу; `valueChanged` → `worker.set_conf`,
  на фото `sliderReleased` → `commit_still`.
- **Панель «Events»**: рядки з сигналу `event`, найновіші внизу, автопрокрутка.
- **Рядок стану**: джерело, кадр `i / N` (камера — `i`), FPS, «N near-miss»; по закінченні —
  підсумок з `finished`.
- **Помилки** (`failed`) — `QMessageBox.warning`, застосунок живий.
- **Закриття вікна**: `stop` → дочекатися завершення потоку робітника → закрити
  (камера звільнена). Якщо UI не встигає — показувати найсвіжіший кадр.
- Усі написи — англійською.

## З брифа, дослівно

> «PySide6: open a file or camera, live view, settings, object list, threshold slider.»
> «For every detected object the app reports its class, a bounding box, and how far the
> object's centre sits from the centre of the frame (dx / dy, in pixels and as a fraction
> of the half-frame).»
> «Target selection: click an object to lock onto it, otherwise auto-select the one
> nearest the frame centre.»
> «Code, comments, logs, README, UI strings | all English»

## Розділи специфікації

Історії 1–27, 36, 43, 46; Рішення: «Перегляд», «Повідомлення про помилки», «Точка входу»,
«Стоп і звільнення камери»; Межі та шви — `ui/view.py`, `ui/main_window.py`, `app.py`.

## Критерії приймання

- [ ] `to_image_point` — тести без Qt: масштаб, поля зверху/збоку, клік поза кадром → `None`
- [ ] `MainWindow` offscreen із робітником на заглушках: відкриття фото заповнює таблицю
      (лише намальовані), рядок near-miss, рядок цілі `TARGET` на потоці
- [ ] Повзунок: діапазон від `conf_debug` (з `conftest.schema_value`), `set_conf` доходить
      до робітника; на фото — `commit_still` при відпусканні
- [ ] Клік у перегляді на потоці → `worker.click` з пікселями кадру
- [ ] `failed` показує повідомлення, вікно живе; `model_failed` — кнопки неактивні
- [ ] Закриття вікна під час потоку-заглушки камери: `Source.close()` викликано, потік
      робітника завершився
- [ ] `app.py --help` працює; битий конфіг — `EXIT_USAGE` без вікна
- [ ] Повний набір тестів зелений
