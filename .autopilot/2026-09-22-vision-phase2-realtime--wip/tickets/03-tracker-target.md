# 03 — Трекінг ByteTrack і вибір цілі

**Вимоги:** R10, R11, R12, R15i, R41, R47, R51, R56i
**Blocked by:** 01
**Зона:** `core/tracker.py` · `core/target.py` · `tests/test_tracker.py` · `tests/test_target.py` · `tests/test_offline.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Детекції з кадру в кадр отримують стабільний `track_id`, а з них вибирається одна
ціль: найближча до центру кадру, або та, на яку клацнув користувач. Обидва модулі
чисті щодо вводу-виводу і перевіряються без моделі. Імпорт трекера не вмикає
мережу.

## З брифа, дослівно

> «ByteTrack for stable `track_id` across frames.»
> «Target selection: click an object to lock onto it, otherwise auto-select the one nearest the frame centre.»
> «YOLO26 is NMS-free. There is no non-maximum-suppression post-processing step. Do not add one»
> «Fully offline at runtime.»

## Розділи специфікації

Історії 12–17, 19, 21; Рішення §5, §6, §11; Межі: `core/tracker.py`, `core/target.py`; Шви 2, 3, 6.

## Що зробити

**`core/tracker.py`** — `Tracker(cfg)`, `update(frame, detections) -> list[Detection]`, `reset()`.

- Перший рядок імпортів проєкту — `import core.detector  # noqa: F401` з коротким
  коментарем чому (офлайн-перемикачі мають бути виставлені до ultralytics).
  `ultralytics` — ліниво в `__init__`: `from ultralytics.trackers.byte_tracker import BYTETracker`,
  `from ultralytics.engine.results import Boxes`.
- Аргументи `BYTETracker` — простий об'єкт (`types.SimpleNamespace`) з полями
  `tracker_type="bytetrack"`, `track_high_thresh = cfg.model.conf`,
  `new_track_thresh = cfg.model.conf`, `track_low_thresh = cfg.model.conf_debug`,
  `track_buffer`, `match_thresh`, `fuse_score` з `cfg.tracker`. Перевір у
  `venv\Lib\site-packages\ultralytics\trackers\byte_tracker.py`, які ще поля
  `args` він читає, і задай їх так само явно.
- `update`: загорнути детекції в `Boxes(np.array([[x1,y1,x2,y2,conf,cls_id], …], dtype=float32), orig_shape=(h, w))`;
  порожній список — масив форми `(0, 6)` (трекер має все одно просунути кадр,
  щоб старіли втрачені треки). Результат `BYTETracker.update` — рядки
  `[x1,y1,x2,y2,track_id,score,cls,idx]`; `idx` — індекс вхідної детекції: цій
  детекції ставиться `track_id` (через `dataclasses.replace`, вхідні об'єкти не
  мутувати). Детекції без треку — `track_id=None`. Порядок і склад повернутого
  списку = вхідний. Рамки й `conf` детекцій не підміняти трекерними — `dx`/`dy`
  рахує `geometry`, і вони мають збігатися з тим, що бачив детектор.
- `reset()` — новий потік, нумерація з початку.
- NMS не додавати; класів не фільтрувати (детектор уже відфільтрував whitelist).

**`core/target.py`** — `Targeting(cfg)`, `TargetState` (форма в `interfaces.md`).

- `choose(detections, frame_size) -> TargetState`. Кандидати — лише детекції з
  `track_id is not None` (виклик передає вже намальовані, ≥ `conf`). Без
  блокування — найменша `dx² + dy²`; нічия — вищий `conf`. Порожньо →
  `TargetState(None, False, False)`.
- `click(point, detections)`: рамки, що містять точку; з них найменша за площею →
  блокування на її `track_id`. Точка поза всіма рамками → зняти блокування.
- Заблокований трек присутній → `TargetState(det, locked=True, lost=False)`.
  Відсутній → `TargetState(None, True, True)` і лічильник +1; коли лічильник
  перевищує `cfg.tracker.track_buffer` (ByteTrack до того часу вже забув id) —
  блокування знято, у тому ж виклику ціль — найближча. Повернувся раніше —
  лічильник скинуто.
- Без вводу-виводу, без `cv2`, без порогів `conf`.

**Тести.**

- `tests/test_tracker.py`: дві синтетичні рамки різних класів рухаються по 5 px за
  кадр 10 кадрів → кожна тримає один `track_id`, id різні; третя рамка з'являється
  на 6-му кадрі → новий id; порожній кадр посередині не ламає `update`; `reset()`
  починає нумерацію знову; вхідні `Detection` не змутовані; `bbox`/`conf` на виході
  = на вході.
- `tests/test_target.py`: найближча до центру; нічия за `conf`; клік по вкладених
  рамках блокує меншу; клік у порожнє — знімає; втрата `track_buffer + 1` кадрів
  знімає блокування, повернення раніше — ні; детекції без `track_id` ігноруються.
- `tests/test_offline.py`: третій сценарій у тому ж стилі (підпроцес) — чистий
  процес імпортує `core.tracker`, створює `Tracker` на тестовому конфігу і робить
  один `update`; сокети не зачеплені, телеметрія вимкнена. Наявні два сценарії не
  змінювати.

## Критерії приймання

- [ ] `track_id` стабільний на рухомих рамках, новий об'єкт — новий id
- [ ] `update([])` не падає і старить треки
- [ ] Ціль без кліку — найближча до центру; клік блокує, клік у порожнє знімає
- [ ] Втрачена заблокована ціль: `lost=True`, інші не підхоплюються, після `track_buffer` кадрів — знову найближча
- [ ] Підпроцесний тест: імпорт і `update` трекера не торкаються мережі
- [ ] `ultralytics` у цих модулях імпортується лише після `core.detector`; уся суїта зелена
