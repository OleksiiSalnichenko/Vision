# 01 — Підготовка `core/`: ключ кольору, запис конфігу, класи й поріг на льоту

**Вимоги:** R08, R08.2, R08.3, R16i, R16i.1, R24, R27, R33, R10.3
**Blocked by:** —
**Зона:** `core/config.py` · `core/detector.py` · `core/tracker.py` · `config.yaml` · `tests/conftest.py` · `tests/test_config.py` · `tests/test_detector.py` · `tests/test_tracker.py`
**Хвиля:** 1
**Status:** ready

## Що має запрацювати

Чотири невеликі доповнення в `core/`, на яких стоїть застосунок. Нічого з наявного
не переписується, `detect.py` не чіпається (його бере таск 02).

1. **Ключ `display.color: false`** — у `config.yaml` (секція `display`, з коментарем як
   у сусідів), у `DisplayConfig`, у `_RULES`, у `tests/conftest.CONFIG_SCHEMA` (значення
   там навмисно інше, ніж у `config.yaml` — див. наявний стиль). Відсутній ключ —
   `ConfigError` з назвою ключа, як у всіх.
2. **`save_values(path, values: dict[str, Any]) -> None`** у `core/config.py`. Ключі —
   крапкові (`"model.conf"`, `"model.weights"`, `"model.imgsz"`, `"display.center_line"`,
   `"display.color"`) і `"classes"` (список). Файл правиться порядково: у рядку
   `key: value   # comment` міняється лише значення, коментар і відступ лишаються;
   закоментовані рядки (`#weights: …`) не чіпаються і не вважаються ключем; список
   `classes` переписується блоком із тими самими відступами (порожній список —
   `classes: []`, з коментарем, якщо він був). Результат пишеться в тимчасовий файл поруч,
   перевіряється `load_config`, і лише тоді `os.replace`. Невідомий ключ, ключ, якого немає
   у файлі, або значення, яке не проходить `_RULES`, — `ConfigError` з назвою ключа, файл
   без змін. Числа форматуються так, щоб `0.5` не ставало `0.50000001`. Читати й писати —
   UTF-8, переноси рядків — як у файлі.
3. **`Detector.names -> dict[int, str]`** (властивість) і **`Detector.set_classes(classes:
   list[str]) -> None`** — той самий `_whitelist_ids`, той самий `ValueError` на невідоме
   ім'я; порожній список — усі класи. Фільтр уже передається в модель на кожен кадр, тож
   перезавантаження не потрібне.
4. **`Tracker.set_conf(conf: float) -> None`** — міняє верхню і «нову» межі ByteTrack
   (`track_high_thresh`, `new_track_thresh`) на льоту, без скидання треків і лічильника id.
   Нижня межа лишається `conf_debug`.

## З брифа, дослівно

> «PySide6: open a file or camera, live view, settings, object list, threshold slider.»
> «Every tunable number lives in `config.yaml`, never as a constant in code.»
> «Classes | whitelist in `config.yaml`, not all 80 COCO classes»
> Доповнення: «у панелі модель `.pt`/OpenVINO, список класів, колір, лінія до центру,
> `imgsz`; зміни діють одразу на сеанс; кнопка «Save to config.yaml» записує змінені
> значення, коментарі у файлі лишаються»: «"а"»

## Розділи специфікації

Історії 30–33; Рішення: «Поріг на потоці», «Класи моделі», «Колір як ключ конфігу»,
«Запис у `config.yaml`»; Межі та шви — рядки `core/tracker.py`, `core/detector.py`,
`core/config.py`.

## Критерії приймання

- [ ] `display.color` є в `config.yaml`, `DisplayConfig`, `_RULES`, `CONFIG_SCHEMA`; тест
      «shipped config carries every schema key» проходить; без ключа — `ConfigError` з назвою
- [ ] `save_values` на копії справжнього `config.yaml` (у `tmp_path`): міняє `model.conf`,
      `classes`, `display.center_line`, `display.color`, `model.weights` — і після цього всі
      коментарі, закоментований рядок `#weights:` і порядок ключів на місці (порівняння
      рядок у рядок, крім змінених); `load_config` читає нові значення
- [ ] `save_values` з невалідним значенням (`model.conf: 1.5`) або невідомим ключем —
      `ConfigError` з назвою ключа, файл байт у байт той самий
- [ ] `Detector.set_classes` / `names` — тест без моделі (через наявну пастку/заглушку
      `YOLO` у `test_detector`): невідоме ім'я — `ValueError`, порожній список — `None`
- [ ] `Tracker.set_conf` — тест: об'єкт із conf між новим і старим порогом отримує
      `track_id` після зниження порогу; наявні треки зберігають свої id
- [ ] `config.yaml`: змінено лише додаванням рядка `display.color`; незакомічена зміна
      користувача в `model.weights` лишилась як є
- [ ] Повний набір тестів зелений
