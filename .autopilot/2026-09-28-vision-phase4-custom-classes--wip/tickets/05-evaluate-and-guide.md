# 05 — Порівняння моделей, наскрізна репетиція і посібник

**Вимоги:** R01, R02, R04, R11, R12, R13, R15, R16, R20, R27, R32, R33, R34, R35, R36, R37, R42i, R38i, G01, G02
**Blocked by:** 02, 03, 04
**Зона:** `training/evaluate.py` · `training/README.md` · `README.md` (лише новий розділ-посилання) · `tests/test_training_evaluate.py` · `tests/test_training_e2e.py`
**Хвиля:** 3
**Status:** ready

## Що має запрацювати

Користувач відкриває `training/README.md` і за ним проходить увесь шлях: акаунт
Kaggle → зйомка → кадри → Label Studio → (груба модель → авторозмітка) → збірка
датасету → навчання → перевірка → підключення одним рядком. Кожен крок — команда і
один рядок «навіщо». Окремий розділ «For the agent» — точна послідовність для
наступної сесії, з місцями, де потрібне «так» користувача. `evaluate` порівнює
моделі на його кадрах. Наскрізний тест проганяє весь ланцюжок на синтетиці.

## З брифа, дослівно

> «зроби всю роботу. дай інстукцію, навіть краще - задокументу. Коли я цим вирішу
> зайнятися - надам всі данні... і ти повчишь можель»
> «Shoot in the conditions the model will actually run in.»
> «Before shooting anything, check whether the class already exists as a labelled
> dataset (Roboflow Universe, Open Images V7 with 600 classes).»
> «Whether `yolo26n` is accurate enough for a pen. Unknown until I test on my own
> photos. The fallback path is `yolo26s`, or `imgsz: 960`, or shooting closer.»

## Розділи специфікації

Історії 1, 3, 15 (посібник: готові датасети, FiftyOne), 19 (посібник: акаунт), 23,
24, 27, 29, 30, 32; Рішення 1–13.

## Критерії приймання

- [ ] `evaluate --weights A [B …] --build NAME [--imgsz N]`: для кожної моделі —
      `YOLO(w).val(data=<build>/data.yaml, device="cpu", imgsz=…)` офлайн
      (`import core.detector` першим), mAP50 і mAP50-95 по класах з `training.classes` і
      загальний; швидкість кадру — середнє `Detector` на кількох val-кадрах; таблиця в
      консоль; моделі з різними `names` (2 vs 82) — порівнює спільні класи за назвою
- [ ] `tests/test_training_e2e.py` (subprocess, пастка сокетів, пропуск без
      `models/yolo26n.pt`): синтетичне відео → `extract_frames` → фейковий експорт LS
      (YOLO, `classes.txt` = pen, flower) → `build_dataset` (Detector — справжня
      `yolo26n.pt`) → `kaggle/train.py --smoke` → `evaluate` на результаті → все з кодом 0
- [ ] `training/README.md` (англійською), розділи: огляд і схема шляху даних; що
      потрібно (Kaggle-акаунт, підтвердження телефону для GPU, API-токен у
      `%USERPROFILE%\.kaggle\kaggle.json` — **користувач кладе сам**, `kaggle.username`);
      зйомка (реальні умови, ракурси, дрібна ручка, негативи, ~10 хв, кожен 20-й);
      готові датасети — **перевір через веб** і назви конкретні на Roboflow Universe /
      Open Images V7 для `pen`/`flower` (назва, посилання, ліцензія, кількість) +
      команди FiftyOne в `venv-labelstudio` для Open Images → YOLO + чому не скрейпінг;
      Label Studio (setup/start/config, створення проєкту, local storage, експорт YOLO);
      груба модель і авторозмітка; збірка датасету; навчання на Kaggle; перевірка
      (`evaluate`, що робити, якщо ручка слабка: ближче, `imgsz: 960` + `export --force`,
      `yolo26s`); підключення (`fetch` → `export_openvino.py --weights` → рядок
      `model.weights`, `classes`, приклад правила `class: pen` у `rules.yaml`);
      відкат на стару модель; «For the agent»; troubleshooting
- [ ] Посібник описує поведінку, яку збудували 02 і 03 (див. `interfaces.md`): `setup`
      пропускає установку лише коли `label-studio.exe` уже є; `start` слухає тільки
      `127.0.0.1` і виставляє `LABEL_STUDIO_COLLECT_ANALYTICS=false`,
      `LABEL_STUDIO_LATEST_VERSION_CHECK=false` (назви обидві, і що Sentry у відкритій версії
      без DSN); `prelabel` працює лише з кадрами під `data/training`; кадри з `--extra` не
      отримують псевдорозмітки 80 класів (люди на них — фон), і перевірка «є рамки нових
      класів» рахує тільки власні кадри
- [ ] Кожна команда в посібнику існує й працює (перевір `--help` кожного скрипта)
- [ ] `README.md`: короткий розділ «Custom classes (phase 4)» з посиланням на
      `training/README.md` — нічого більше в ньому не міняти
- [ ] Повний набір тестів зелений
