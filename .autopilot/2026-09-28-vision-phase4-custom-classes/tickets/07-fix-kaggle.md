# 07 — Виправлення: шлях Kaggle і межа офлайн/мережа

**Вимоги:** R09, R10, R24, R43i, G02
**Blocked by:** 05
**Зона:** `training/kaggle_run.py` · `training/kaggle/train.py` · `tests/test_training_{kaggle_run,train,boundaries,smoke}.py`
**Хвиля:** 4 (паралельно з 06; 06 володіє `training/prelabel.py`, `build_dataset.py`, `label_studio.py`, `evaluate.py`, `training/README.md` і їхніми тестами — їх не чіпати)
**Status:** ready

## Звідки

Незаблокуючі знахідки рев'ю тасків 01, 04, 05, відібрані на виправлення у фазі 8. Кожна
помилка тут проявилася б лише після пушу — на GPU-годинах користувача.

## Критерії приймання

- [ ] `train.py` `find_dir` (пошук під `/kaggle/input` до 4 рівнів, маркер з підшляхом) покрито
      тестом на тимчасовому дереві: знаходить на різній глибині, не знаходить глибше межі, без
      маркера — одне речення.
- [ ] `kaggle_run`: збій `kaggle` CLI → код 1 з одним реченням; `fetch` без `best.pt` у виході
      ядра → одне речення. Тести на обидва шляхи (фейковий `KAGGLE_EXE`).
- [ ] `kaggle datasets status`: «датасету нема» відрізняється від збою авторизації/мережі; збій —
      одне речення про причину, без спроби `create`. Тест.
- [ ] `upload --yes` не лишає `dataset-metadata.json` у build-теці користувача (тимчасова
      staging-тека або прибирання після; формат build з `interfaces.md` незмінний). Тест.
- [ ] Невідповідність вставки `settings.py` у пушений `train.py` (`RuntimeError`) — одне речення
      і код 2 у `main`, без traceback. Тест.
- [ ] `ULTRALYTICS_PIN` у `train.py` дорівнює піну `ultralytics` у `requirements.txt` — тест.
- [ ] Збій навчання на Kaggle друкує повний traceback Ultralytics у лог ядра (зараз
      `except (OSError, ValueError, KeyError)` ховає його), код ненульовий.
- [ ] `tests/test_training_boundaries.py`: дозволені імпорти офлайн → мережевих модулів названі
      явно (`evaluate` → `kaggle.train`, `prelabel` → `label_studio`); тест, що імпорт
      `training.kaggle.train` і `training.label_studio` не робить мережевих дій на рівні модуля
      (пастка сокетів у підпроцесі).
- [ ] Повний набір тестів зелений; кількість тестів зросла.
