# 02 — Label Studio: установка, запуск, інтерфейс розмітки, авторозмітка

**Вимоги:** R07, R14, R23, R31, R28
**Blocked by:** 01
**Зона:** `training/label_studio.py` · `training/prelabel.py` · `tests/test_training_label_studio.py` · `tests/test_training_prelabel.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Користувач однією командою ставить Label Studio в окремий `venv-labelstudio` у
корені проєкту (не системно), другою — запускає його так, що він бачить кадри з
`data/training/frames` і нікуди їх не шле, третьою — отримує XML інтерфейсу
розмітки з рамками для `pen` і `flower`, який вставляє в налаштування проєкту.
Коли є груба модель, `prelabel` готує файл завдань з її передбаченнями, і
користувач лише виправляє рамки замість малювати з нуля.

## З брифа, дослівно

> «annotate in Label Studio» / «Runs locally via pip. Data never leaves the machine.»
> «annotate the first 50 images by hand, train a rough model, let it pre-annotate
> the remaining 450, then correct its mistakes»
> «Instance segmentation | Boxes only.»
> «Ask before installing anything system-wide.»

## Розділи специфікації

Історії 8, 9, 16 (частина `prelabel`), 26, 31; Рішення 3, 11; Межі: `label_studio.py`,
`prelabel.py`.

## Критерії приймання

- [ ] `label_studio.py setup`: `py -3.11 -m venv venv-labelstudio` + pip install
      `label-studio` у нього; якщо venv уже є — пропуск з рядком `skip: …`; без `py` →
      речення + 2. У тестах `subprocess.run` підмінено — нічого не ставиться
- [ ] `label_studio.py start`: без `venv-labelstudio` → речення «run training/label_studio.py
      setup first» + 2; інакше запускає `venv-labelstudio\Scripts\label-studio start` з
      `--host localhost`, змінними `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true`,
      `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=<абсолютний data/training>` і змінними
      вимкнення аналітики. **Знайди їх** у документації Label Studio (WebFetch
      labelstud.io) і запиши в коментар біля коду з посиланням; якщо вимикача нема —
      коментар каже це прямо. Тест перевіряє склад команди і середовища на підміненому
      `subprocess`
- [ ] `label_studio.py config`: друкує XML з `<Image>` і `<RectangleLabels>` з
      `training.classes` (лише рамки); `labeling_config(classes)` — чиста функція з тестом
- [ ] `prelabel --weights W --frames DIR [--out tasks.json]`: проганяє модель
      (`core.detector.Detector` з `dataclasses.replace` на `model.weights=W`,
      `classes=[]`) по кадрах **без файлу розмітки** в експорті, якщо передано
      `--skip-labelled EXPORT`; пише JSON імпорту LS: `data.image` = URL локальних файлів
      (`/data/local-files/?d=frames/<stem>/<file>`), `predictions[].result[]` —
      `rectanglelabels` у відсотках від ширини/висоти; лише класи з `training.classes`
- [ ] `tasks(...)` — чиста функція з тестом на відомих рамках (піксельні → відсоткові)
- [ ] Модель у тестах — заглушка; жодного справжнього Label Studio, жодної мережі
- [ ] Модулі додані в список офлайн-перевірки `tests/test_training_boundaries.py`
      (`prelabel.py` — офлайн; `label_studio.py` — у списку мережевих)
- [ ] Повний набір тестів зелений
