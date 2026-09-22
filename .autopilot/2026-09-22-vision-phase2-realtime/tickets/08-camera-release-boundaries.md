# 08 — Камера звільняється завжди, межі модулів цілі

**Вимоги:** R05, R32, R40i, R41, R48
**Blocked by:** 01–07
**Зона:** `core/source.py` · `detect.py` · `core/detector.py` · `core/events.py` · `tests/test_source.py` · `tests/test_detect_cli.py` · `tests/test_bench.py` · `tests/test_events.py`
**Хвиля:** 4
**Status:** ready

## Навіщо

Зауваження, що повторились у трьох тасках (02, 05, 07), зведені у фінальному
розборі. Під час збірки користувач помітив, що вебкамера лишилась увімкненою:
зависла перевірка тримала її відкритою. Код досі покладається на збирач сміття,
щоб звільнити камеру, і на одному шляху не звільняє її зовсім.

## З брифа, дослівно

> «Video and webcam branches in `Source`.»
> «Fully offline at runtime.»
> «Phase 2 layers rule evaluation and debouncing on top of this same bus without changing its signature.»

## Що зробити

1. **`Source` звільняє ресурс явно.** `close()` (ідемпотентний) і контекстний
   менеджер (`with Source(...) as source:`). Повторна ітерація вже закритої камери
   — `RuntimeError("source already consumed: camera N")`, а не «stopped
   delivering frames» (це неправда про камеру). Фото/тека: `close()` нічого не
   робить.
2. **`detect.py`**:
   - `Source` відкривається в `with` (або `try/finally: source.close()`) —
     камера звільняється на **кожному** шляху: кінець, `q`/`Esc`, Ctrl+C, збій,
     помилка `rules.yaml`/`handlers.py` на старті.
   - `rules.yaml` і `handlers.py` перевіряються **до** відкриття камери, де це
     можливо (помилка правил не має вмикати камеру взагалі).
   - `except OSError` у циклі потоку — лише навколо читання кадру (помилка
     камери → код 1, «camera stopped»); `OSError` запису файлів — одне речення
     про файл, код 2. Повідомлення відповідає тому, що зламалось.
   - Відео чи камера — питати `Source` (додай у `Source` публічне
     `is_camera: bool` або `kind`), а не `Path(args.source).is_file()` заново.
3. **`core/events.py`**: публічна `subscriptions(name) -> set[str | None]` —
   класи, на які підписані обробники з цим ім'ям. `detect.py` більше не читає
   `events._handlers`.
4. **`core/detector.py`**: `sys.modules["openvino_telemetry"] = None` — пряме
   присвоєння, не `setdefault` (якщо пакет уже імпортовано раніше, `setdefault`
   мовчки лишає телеметрію ввімкненою). Якщо пакет уже в `sys.modules` як модуль
   — `log.warning`, що вимкнення запізнилось.
5. **Тести:**
   - `tests/test_bench.py`: випадки `"0"` і `"camera:0"` підміняють
     `bench.Source` (і `core.source.open_camera`) пасткою, що падає, — регресія
     має почервоніти, а не відкрити камеру.
   - `tests/test_detect_cli.py`: `StubSource`, що кидає `OSError` камери посеред
     потоку → код 1, writer закритий, `close()` джерела викликано, підсумок
     надруковано; `KeyboardInterrupt` → код 0, те саме; помилка `rules.yaml` →
     код 2 і `close()` викликано (або джерело не відкривалось).
   - `tests/test_source.py`: `close()` ідемпотентний; повторна ітерація закритої
     камери → `RuntimeError` (через підмінений `open_camera`, без справжньої камери).
   - `tests/test_events.py`: `subscriptions`.

**Жоден тест не відкриває справжню камеру чи вікно.**

## Критерії приймання

- [ ] На кожному шляху виходу з потоку `Source.close()` викликано — тестом
- [ ] Помилка `rules.yaml` не вмикає камеру
- [ ] Помилка запису файлу і збій камери дають різні повідомлення й коди
- [ ] `detect.py` не читає приватний реєстр `core/events.py`
- [ ] Телеметрію OpenVINO вимкнено присвоєнням; тест офлайну зелений
- [ ] `tests/test_bench.py` не може відкрити справжню камеру навіть при регресії
- [ ] Уся суїта зелена
