# 04 — Навчання на Kaggle: скрипт навчання, CLI-обгортка, smoke

**Вимоги:** R09, R10, R17, R19, R21, R22, R26, R39i, R40i, G02, G03
**Blocked by:** 01
**Зона:** `training/kaggle_run.py` · `training/kaggle/` · `tests/test_training_kaggle_run.py` · `tests/test_training_train.py` · `tests/test_training_smoke.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Агент (з «так» користувача) однією командою заливає build-теку на Kaggle як
приватний датасет, другою запускає на GPU навчання, третьою стежить за станом,
четвертою забирає `best.pt` і `metrics.json` у `models/`. Без `--yes` кожна мережева
команда лише показує план. Скрипт навчання той самий на Kaggle і локально:
локальний smoke-прогін на CPU доводить, що 82-класова модель навчається,
експортується в OpenVINO і читається `Detector` з 82 іменами.

## З брифа, дослівно

> «fine-tune on Kaggle, download `best.pt`»
> «Training must happen in the cloud.»
> «Kaggle (free P100, 30 GPU-hours/week, private datasets) is the chosen provider.»
> «if phase 4 shows `n` cannot handle them, switching to `s` must not require a network connection»
> «тоді А» (на «через `kaggle` CLI: ключ кладеш сам, я заливаю і запускаю; кожну заливку — з твого "так"»)

## Розділи специфікації

Історії 4, 5, 17–22; Рішення 1, 4–8, 13; формати build-теки і виходу навчання в
`interfaces.md`.

## Критерії приймання

- [ ] `kaggle/train.py --data-root D --out O [--coco-root C] [--smoke]`: читає
      `D/training.yaml`, `D/data.yaml`, ваги з `D`; з `--coco-root` бере
      `coco.train_images`/`coco.val_images` випадкових зображень, конвертує COCO JSON →
      YOLO **за назвою категорії** в ID 0–79 з `data.yaml` (тест на синтетичному
      `instances_*.json` з 3 категоріями в іншому порядку); зливає в робочу теку;
      навчає `ultralytics.YOLO(weights).train(...)` з `train.*` (у `--rough` — `rough.epochs`);
      пише `O/best.pt`, `O/metrics.json` (формат з `interfaces.md`), COCO-mAP до/після
- [ ] `--smoke`: `YOLO_OFFLINE=1` до імпорту ultralytics, `device=cpu`, 1 епоха, крихітний
      `imgsz` (32 або 64), без COCO
- [ ] `tests/test_training_smoke.py`: subprocess з пасткою сокетів (як `tests/test_offline.py`):
      синтетична build-тека (2–4 кадри з намальованими прямокутниками, 82 імена) →
      `train.py --smoke` → `best.pt` має `names` довжиною 82 з `pen`/`flower` на 80/81 →
      `scripts/export_openvino.py --weights <best.pt>` → `Detector` на OpenVINO-теці віддає
      `names` 82 і `set_classes(["pen"])` не падає. Пропуск, якщо нема `models/yolo26n.pt`.
      Тест може бути повільним — познач `@pytest.mark.slow` лише якщо в проєкті вже є
      такий маркер; інакше просто тест
- [ ] `kaggle_run.py check`: exe `kaggle` знайдено? `%USERPROFILE%\.kaggle\kaggle.json`
      **існує** (вміст не читати, не друкувати)? `training.kaggle.username` непорожній? —
      по реченню на проблему, код 2; все гаразд — `ok`
- [ ] `upload --build NAME [--yes]`: без `--yes` — план (тека, розмір МБ, `username/dataset_slug`,
      приватний) і код 0; з `--yes` — `dataset-metadata.json` у тимчасовій теці/поряд і
      `kaggle datasets create -p … --dir-mode zip` (вперше) або `kaggle datasets version
      -p … -m <msg> --dir-mode zip` (як визначити «вперше» — `kaggle datasets status`)
- [ ] `train [--rough] [--yes]`: план; з `--yes` — тимчасова тека з `train.py` і
      `kernel-metadata.json` (`kernel_type: script`, `is_private: true`, `enable_gpu: true`,
      `enable_internet: true`, `dataset_sources`: датасет користувача + `kaggle.coco_dataset`
      (без COCO в `--rough`)), `kaggle kernels push -p …`. Скрипт на Kaggle ставить
      `ultralytics==8.4.157` через pip і знаходить теки джерел під `/kaggle/input/…`
- [ ] **Перевір через веб (WebFetch/WebSearch)**, що `awsaf49/coco-2017-dataset` існує і
      як усередині лежать зображення та `instances_*2017.json`; зафіксуй шляхи в
      `train.py`; якщо не так — знайди інший публічний COCO-2017 і зміни
      `kaggle.coco_dataset` у `training.yaml`. Запиши, що знайшов, у звіті таска
- [ ] `status`: `kaggle kernels status username/kernel_slug`; `fetch --name N [--force]`:
      `kaggle kernels output … -p <tmp>` → `models/N.pt`, `models/N.metrics.json`, друкує
      sha256 і рядок `model.weights: models/N.pt` та команду експорту; існуючий без
      `--force` → речення + 2
- [ ] Усі виклики exe — через `KAGGLE_EXE`; тести підставляють фейковий скрипт, що пише
      свої аргументи у файл; жоден тест не викликає справжній `kaggle`
- [ ] `kaggle_run.py` і `kaggle/train.py` — у списку мережевих модулів
      `tests/test_training_boundaries.py`
- [ ] Повний набір тестів зелений
