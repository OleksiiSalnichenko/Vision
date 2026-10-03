# 01 — Основа `training/`: конфіг, класи, кадри з відео

**Вимоги:** R01, R03, R05, R06, R24, R25, R29, R30, R43i, G01, G03
**Blocked by:** —
**Зона:** `training/__init__.py` · `training/settings.py` · `training/classes.py` · `training/extract_frames.py` · `training/training.yaml` · `requirements-training.txt` · `.gitignore` · `tests/test_training_settings.py` · `tests/test_training_classes.py` · `tests/test_training_frames.py` · `tests/test_training_boundaries.py`
**Хвиля:** 1
**Status:** ready

## Що має запрацювати

Папка `training/` існує як пакет, на який спираються всі наступні таски.
Користувач кладе відео в будь-яку теку (навіть з кириличною назвою) і однією
командою отримує кожен 20-й кадр у `data/training/frames/<stem>/`, з підсумком,
скільки кадрів уже є і скільки до цілі ~900. Усі числа фази 4 живуть у
`training/training.yaml` і завантажуються строго. Порядок 82 імен класів
визначається одним місцем.

## З брифа, дослівно

> «Method: shoot 10 minutes of video of the object from many angles, take every
> 20th frame (~900 images with natural variation in angle, blur and lighting)»
> «Custom classes (a pen, flowers) are needed later, so the pipeline must support
> fine-tuning without being restructured.»
> «просто, навчені обьєкти додай додавай в список»

## Розділи специфікації

Історії 2 (порядок імен), 6, 7, 25, 31; Рішення 2, 8, 10, 12, 13; ключі
`training.yaml`; Межі: `settings.py`, `classes.py`, `extract_frames.py`.

## Критерії приймання

- [ ] `training/training.yaml` має всі ключі зі специфікації (розділ «Рішення щодо
      реалізації», абзац про ключі) з коментарем-поясненням кожного; `kaggle.username: ""`
      з коментарем «your Kaggle login — fill in after creating the account»
- [ ] `load_training(path)`: відсутній ключ → `TrainingConfigError` з повною назвою
      ключа (`dataset.val_fraction`); неправильний тип/діапазон → так само; невідомий
      ключ → попередження в лог; кожен ключ має правило (тип + діапазон) — тест
      параметризований по всіх ключах
- [ ] `class_names(base, custom)` → список 82: базові в порядку ID, потім кастомні;
      кастомне ім'я, що вже є в базових, → `ValueError` з назвою
- [ ] `extract_frames --video V [--out DIR] [--force]`: кадри з індексом, кратним
      `frames.step`, у `data/training/frames/<stem>/<stem>_<index:06d>.jpg`; читання через
      `core.source.Source`; запис `imencode` + `write_bytes`; тест на крихітному відео в
      `tmp_path`, у т.ч. з кириличною назвою; непорожня тека без `--force` → речення + 2;
      відсутнє відео → речення + 2
- [ ] Підсумок: `wrote N frames to …` і `total M frames in data/training/frames (target ~T)`
- [ ] `requirements-training.txt` з `kaggle` (пін на поточну стабільну версію — перевір
      через `venv\Scripts\python -m pip index versions kaggle` **не можна** (мережа):
      постав без піна з коментарем, що версія фіксується при першій установці);
      `.gitignore` + `venv-labelstudio/`
- [ ] `tests/test_training_boundaries.py`: AST-скан `core/` — жодного імпорту `training`;
      локальні модулі `training/` (крім `kaggle_run.py`, `label_studio.py`,
      `kaggle/train.py`) не імпортують `socket`/`requests`/`urllib`/`kaggle` (тест
      розширюваний: наступні таски додають свої модулі в список)
- [ ] Повний набір тестів зелений
