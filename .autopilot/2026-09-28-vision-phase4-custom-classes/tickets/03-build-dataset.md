# 03 — Збирач датасету: експорт LS + псевдорозмітка + спліт + build-тека

**Вимоги:** R08, R12, R13, R15, R16, R18, R36, R41i, G03, R14
**Blocked by:** 01
**Зона:** `training/build_dataset.py` · `tests/test_training_build.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

Користувач віддає експорт Label Studio (теку або zip у форматі YOLO) і отримує одну
готову до заливки теку `data/training/build/<name>/` у форматі з `interfaces.md`.
Ручні рамки `pen`/`flower` отримують ID 80/81; люди, телефони та інші 80 класів на
його кадрах розмічаються поточною моделлю; кадри без рамок — негативи. Готовий
зовнішній датасет можна домішати так, щоб він склав ~20% набору. Режим `--rough`
збирає маленький датасет лише з двох нових класів для грубої моделі.

## З брифа, дослівно

> «export in YOLO format»
> «Include negative frames: the desk with no pen, the room with no flowers.»
> «Internet images may be mixed in at around 20% for variety, but the core of the
> set must be your own frames.»
> «To detect `person` and `pen` together, either include both in the training set»
> «просто, навчені обьєкти додай додавай в список»

## Розділи специфікації

Історії 10–16 (у 16 — `--rough`), 12; Рішення 1, 8, 9; формат build-теки в
`interfaces.md`.

## Критерії приймання

- [ ] `read_ls_export(path)` читає теку або zip (`images/`, `labels/`, `classes.txt`);
      клас у `classes.txt` поза `training.classes` → речення з назвою + 2; зображення
      без `.txt` — немає розмітки (у повному режимі пропускається з лічильником, у
      `--rough` теж), порожній `.txt` — негатив
- [ ] Ремап ID: `classes.txt`-індекси → позиції в `class_names(Detector.names, training.classes)`
- [ ] `pseudo_labels`: `core.detector.Detector` (через `dataclasses.replace`:
      `classes=[]`, поріг — `training.dataset.pseudo_conf`), лише ID 0–79; рамка з IoU ≥
      `pseudo_iou_drop` з будь-якою ручною рамкою відкидається; тест на заглушці з
      відомими рамками
- [ ] `split`: по кожному відео (stem у назві кадру) останні `val_fraction` кадрів за
      індексом → val; зовнішні — окремо тим самим відсотком з `seed`; детермінований;
      відео з 1 кадром → train
- [ ] `--extra DIR`: YOLO-датасет з `classes.txt` або `data.yaml`; бере
      `round(own × f / (1 − f))` випадкових (seed) зображень, де є хоч одна рамка класу з
      `training.classes`, решта рамок відкидається; менше доступних → бере всі +
      попередження
- [ ] `write_build` пише рівно формат з `interfaces.md` (data.yaml з відносними шляхами,
      копія `training.yaml`, копія `training.base_weights`, `manifest.json`); існуюча тека
      без `--force` → речення + 2; з `--force` — тека спершу очищається
- [ ] Підсумок: зображень train/val, рамок по класах, частка негативів; частка нижче
      `min_negative_fraction` → попередження; жодної рамки `pen`/`flower` → речення + 2
- [ ] `--rough`: тільки розмічені кадри, `names` = `training.classes` з ID 0..k-1, без
      псевдорозмітки, `--extra` заборонено (речення + 2), `manifest.json` `mode: rough`
- [ ] Читання/запис зображень — `np.fromfile`/`imdecode`, копіювання файлів — `shutil`;
      кириличні шляхи — тест
- [ ] Модуль у списку офлайн-перевірки `tests/test_training_boundaries.py`
- [ ] Повний набір тестів зелений
