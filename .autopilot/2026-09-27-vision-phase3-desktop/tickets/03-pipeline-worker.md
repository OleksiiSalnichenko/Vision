# 03 — Робітник у фоновому потоці: модель, джерела, стоп, пауза, поріг

**Вимоги:** R13i, R17i, R18i, R05, R05.1, R05.2, R05.3, R06, R06.1, R06.2, R10, R10.1, R10.2, R10.3, R16i, R19i, R34i, A01
**Blocked by:** 02, 05
**Зона:** `ui/worker.py` · `tests/test_ui_worker.py` · після D01 ще `core/pipeline.py` (+ `redraw`) · `core/output.py` (+ `format_event`, `format_summary`) · `tests/test_pipeline.py` · `tests/test_output.py` · після ремонту 1 ще `core/target.py` (`choose(..., new_frame)`) · `tests/test_target.py`
**Хвиля:** 3
**Status:** ready

## Що має запрацювати

`ui/worker.py` — `PipelineWorker(QObject)`, що живе в окремому `QThread` і володіє
моделлю, джерелом і сеансом потоку. UI-потік (таск 04) лише шле йому команди й отримує
результати сигналами. Контракт слотів, сигналів і `FramePayload` — `interfaces.md`, рядок
`ui/worker.py`.

- **Модель**: `load_model()` будує `Detector` через `detector_factory(cfg)` (у проді —
  `core.detector.Detector`); `model_ready(names)` або `model_failed(речення)` —
  `run scripts/fetch_models.py first` / `run scripts/export_openvino.py first`. Модель
  живе між джерелами.
- **Відкриття** `open_source(spec)`: якщо щось іде — спершу зупинити й закрити. Порядок як
  у `detect.main`: `prepare_rules` (`core.pipeline`, лише для потоку, шляхи
  `PROJECT_ROOT / cfg.rules.file` і `HANDLERS_PATH` з `detect.py`) → `require_weights` →
  `source_factory(spec, cfg)` → цикл. Помилка будь-якого кроку — `failed(одне речення)`,
  камера не вмикається.
- **Фото / тека**: кожне фото — `process_still` + `save_still` + `events.emit` для
  намальованих; результат кешується на сеанс джерела. Тека — команди `show_index(i)`
  (Prev/Next) без повторного прогону моделі для вже обробленого фото. `total` у payload —
  `len(source)`.
- **Потік** (відео/камера): `StreamSession` з `on_log`, який шле сигнал `event(рядок)` —
  той самий рядок, що друкує `output.print_event` (рядок будувати через `core.output`, не
  копіювати формат). Кожен кадр — `frame_ready(FramePayload)`. Кінець файлу —
  `finished(підсумок)` у форматі `print_stream_summary`. Камера перестала віддавати кадри
  (`OSError` при читанні) — `failed(речення)` і `finished(підсумок)`. Файл не пишеться
  (`OSError` при записі) — те саме.
- **Стоп / пауза / клік**: прапорець зупинки між кадрами; `finally` закриває сеанс і
  `Source.close()` на кожному шляху. Пауза — лише для відеофайлу: цикл стоїть, клік
  (`click(x, y)` → `StreamSession.click`) і поріг усе одно перемальовують останній кадр.
- **Поріг** `set_conf(conf)`: фото — `resplit_still` для поточного фото, файли фото
  переписуються окремою командою `commit_still()` (UI шле її, коли повзунок відпущено);
  потік — `StreamSession.retune` з наступного кадру.
- **Налаштування** `apply(cfg)`: робітник сам вирішує — змінились модель чи `imgsz` →
  перезавантажити детектор (фото перерахувати; потік — `set_detector`, не скидати);
  змінились класи → `Detector.set_classes`; дисплей/колір → `retune`. Модель не
  завантажилась — лишається стара, `model_failed(речення)`.
- `FramePayload.canvas` — копія масиву; UI не має ділити пам'ять із робітником.

`ui/` у цьому таску не має віджетів. PySide6 і pytest-qt уже в venv (таск 05).

## З брифа, дослівно

> «PySide6: open a file or camera, live view, settings, object list, threshold slider.»
> «Fully offline at runtime. … Never at inference time.»
> Доповнення: «як `detect.py` — правила з `rules.yaml` спрацьовують, події видно в панелі
> «Events», файли в `out\` пишуться як зараз»: «ок.. а .. го»

## Розділи специфікації

Історії 2, 4–15, 23–27, 32, 35–40; Рішення: «Потоки», «Стоп і звільнення камери»,
«Порядок перевірок», «Фото і теки», «Поріг на потоці», «Налаштування — панель»;
Межі та шви — `ui/worker.py`, шов 2.

## Критерії приймання

- [ ] Тести offscreen (`QT_QPA_PLATFORM=offscreen`) з `detector_factory`/`source_factory`-
      заглушками і `qtbot.waitSignal`: фото, тека (Prev не кличе детектор вдруге), відео
      до кінця з `finished`, події в сигналі `event`
- [ ] Камера-заглушка: стоп, відкриття іншого джерела, камера що падає посеред потоку,
      помилка запису — `close()` викликано на кожному шляху
- [ ] Битий `rules.yaml` / невідомий handler — `failed`, `source_factory` не викликано;
      відсутні ваги — `model_failed` з точним реченням
- [ ] `set_conf` на фото міняє поділ без виклику детектора; `commit_still` переписує
      `.json`; на потоці — наступний кадр з новим порогом
- [ ] `apply`: зміна класів — `set_classes`, без нової фабрики; зміна моделі —
      фабрика викликана, треки на потоці не скинуто; невдале завантаження — стара модель
- [ ] Пауза відеофайлу: кадри не йдуть, клік міняє ціль на показаному кадрі
- [ ] Жоден тест не відкриває справжню камеру і не вантажить модель
- [ ] Повний набір тестів зелений
