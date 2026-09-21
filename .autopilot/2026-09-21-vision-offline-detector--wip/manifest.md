# Маніфест вимог

Джерело: `2026-09-21-brief.md` (дослівний `PROJECT_PROMPT.md` + рядок у чаті)
та `ARCHITECTURE.md` §6–9 як нормативне джерело за посиланням.
Рядок з цього списку може зняти **тільки користувач**.

Позначки: `i` — мається на увазі, в брифі не сказано прямо. `G` — додано користувачем
після брифа. `D` — відкрито збіркою.

Після брифінгу (2026-09-21) невирішених питань не лишилось. Після специфікації
і плану (2026-09-21) кожна жива вимога має таск; точний розділ специфікації —
у `spec.md` §Покриття маніфесту.

## Обсяг і продукт

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R01 | «працюємо тальки над фазами 0 - 0.5 - 1» | in-ticket | — | spec §Покриття → T06 |
| R02 | «a local, offline object detection application in `D:\Projects\Vision`» | in-ticket | — | spec §Покриття → T04, T06 |
| R03 | «For every detected object the app reports its class, a bounding box, and how far the object's centre sits from the centre of the frame (dx / dy, in pixels and as a fraction of the half-frame)» | in-ticket | — | spec §Покриття → T04 |
| R04 | «A crosshair marks the frame centre, a dot marks each object's centre, and a line joins them» | in-ticket | суперечність з ARCHITECTURE §8 знята брифінгом: користувач обрав «Прапорець у config.yaml, типово вимкнено» → `display.center_line: false` (див. G01) | spec §Покриття → T05 |
| R05 | «Phase 1 works on still images only. Video, tracking and a GUI come later.» | in-ticket | — | spec §Покриття → T06 |
| R06 | «Stop after each phase and show me what to run.» | in-ticket | — | spec §Покриття → T06 |

## Жорсткі вимоги

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R07 | «Fully offline at runtime. The network is used exactly twice in the whole project: `pip install`, and a one-time weight download. Never at inference time.» | in-ticket | — | spec §Покриття → T02 |
| R08 | «Must eventually run on a Raspberry Pi. The Pi sets the performance budget, not the laptop.» | in-ticket | діє як обмеження вибору моделі | spec §Покриття → T04 |
| R09 | «Personal learning project, not commercial. AGPL-3.0 is fine.» | in-ticket | — | spec §Покриття → T01 |
| R10 | «Custom classes (a pen, flowers) are needed later, so the pipeline must support fine-tuning without being restructured.» | in-ticket | діє як обмеження структури | spec §Покриття → T04 |
| R11 | «No NVIDIA GPU, so no CUDA» + «Hardware (already measured, do not re-check)» | in-ticket | — | spec §Покриття → T01 |
| R12 | «The machine currently has Python 3.7.3, which is too old — leave it alone and install 3.11 alongside it» | in-ticket | — | spec §Покриття → T01 |

## Ухвалені рішення (не переглядаються)

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R13 | «Python 3.11, fresh venv inside the project» | in-ticket | — | spec §Покриття → T01 |
| R14 | «**Ultralytics YOLO26n**, one model for every phase» | in-ticket | — | spec §Покриття → T02 |
| R15 | «`yolo26s.pt`, downloaded but unused, kept for offline availability» | in-ticket | — | spec §Покриття → T02 |
| R16 | «display/events at 0.5; JSON also records everything down to 0.25» | in-ticket | — | spec §Покриття → T04 |
| R17 | «`imgsz: 640` (the model's native training size)» | in-ticket | — | spec §Покриття → T03 |
| R18 | «whitelist in `config.yaml`, not all 80 COCO classes» | in-ticket | — | spec §Покриття → T03 |
| R19 | «Phase 1 output \| OpenCV window + console lines + annotated JPG + JSON» | in-ticket | — | spec §Покриття → T05, T06 |
| R20 | «in phase 1, but behind a `--color` flag, in its own module» | in-ticket | — | spec §Покриття → T05 |
| R21 | «Code, comments, logs, README, UI strings \| **all English**» | in-ticket | — | spec §Покриття → T01, T03, T05 |
| R22 | «GUI \| PySide6, phase 3, not before» | deferred | поза обсягом цього прогону (R01) | звіт |
| R23 | «Training \| Kaggle notebooks, free GPU» | deferred | фаза 4, поза обсягом (R01) | звіт |
| R24 | «Annotation \| Label Studio, local» | deferred | фаза 4, поза обсягом (R01) | звіт |

## Поза обсягом за словами користувача

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R25 | «Deliberately out of scope: Face recognition. Instance segmentation (boxes only). Handwriting OCR. C++.» | dropped | користувач: «Deliberately out of scope» | — |
| R26 | «Servo hardware — but `core/aim.py` exists as a stub taking `aim(dx, dy)`, so adding real pan-tilt servos later touches one file» | in-ticket | саме заглушка в обсязі; реальні сервоприводи — ні | spec §Покриття → T04 |
| R27 | «`rules.yaml` is deferred to phase 2» | deferred | користувач: «deferred to phase 2» | звіт |

## Пастки, названі користувачем

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R28 | «`config.yaml` stores an explicit path (`models/yolo26n.pt`), and `Detector.__init__` must raise `FileNotFoundError: run scripts/fetch_models.py first` when the file is missing. It must never fall back to the network.» | in-ticket | — | spec §Покриття → T04 |
| R29 | «Switching is one config line. Do not build abstraction around "model selection".» | in-ticket | — | spec §Покриття → T04 |
| R30 | «**YOLO26 is NMS-free.** ... Do not add one; do not port NMS code from YOLO11 examples.» | in-ticket | — | spec §Покриття → T04 |
| R31 | «**`core/` must not import from `ui/`** or know how it was launched.» | in-ticket | — | spec §Покриття → T04 |
| R32 | «Do not skip `conf_debug`. Recording near-miss detections between 0.25 and 0.5 in the JSON» | in-ticket | — | spec §Покриття → T04 |

## Фаза 0 — середовище

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R33 | «Install Python 3.11 (alongside 3.7, not on PATH)» | in-ticket | спосіб обрано брифінгом: «Інсталятор з python.org», `/passive InstallAllUsers=0 PrependPath=0` | spec §Покриття → T01 |
| R34 | «`git init`» | in-ticket | — | spec §Покриття → T01 |
| R35 | «`.gitignore` covering `venv/`, `models/*.pt`, `out/`, `data/`» | in-ticket | — | spec §Покриття → T01 |
| R36 | «a venv in the project» | in-ticket | — | spec §Покриття → T01 |
| R37 | «`ultralytics opencv-python pyyaml numpy scikit-learn`» | in-ticket | — | spec §Покриття → T01 |
| R38 | «Done when `python -c "import torch, cv2, ultralytics"` succeeds.» | in-ticket | — | spec §Покриття → T01 |
| R39 | «Ask before installing anything system-wide.» | in-ticket | виконано для Python 3.11 (брифінг 2026-09-21); діє далі на все системне | spec §Покриття → T01 |

## Фаза 0.5 — ваги

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R40 | «`scripts/fetch_models.py`: download `yolo26n.pt` and `yolo26s.pt` into `models\`» | in-ticket | — | spec §Покриття → T02 |
| R41 | «write SHA256 sums to `models\checksums.txt`» | in-ticket | — | spec §Покриття → T02 |
| R42 | «print a summary» | in-ticket | — | spec §Покриття → T02 |

## Фаза 1 — детекція на нерухомих зображеннях

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R43 | «The structure, module contracts, data flow and config schema are specified in sections 6 to 9 of `ARCHITECTURE.md`. Follow them.» | in-ticket | — | spec §Покриття → T03 |
| R44 | «`detect.py bench.py scripts/{fetch_models,grab}.py core/{types,config,source,detector,geometry,attributes,draw,events,output,aim}.py`» | in-ticket | — | spec §Покриття → T06 |
| R45 | «Roughly 700 lines» | in-ticket | орієнтир, не мета | spec §Покриття → T06 |
| R46 | «`python detect.py --source data/test_images/bus.jpg`» | in-ticket | — | spec §Покриття → T06 |
| R47 | «verify in this order: a stock Ultralytics sample image ... then my own photos ... then the flags, then `scripts/grab.py`» | in-ticket | — | spec §Покриття → T06 |
| R48 | ARCH §7: `Detection` з полями `cls_id, cls_name, conf, bbox, center, dx, dy, dx_pct, dy_pct, color`; «`Detection` is the only type that crosses module boundaries» | in-ticket | — | spec §Покриття → T03 |
| R49 | ARCH §7: «`class Source: def __iter__(self) -> Iterator[Frame]`» — один інтерфейс; «Phase 1 implements the first two» (зображення і тека) | in-ticket | — | spec §Покриття → T04 |
| R50 | ARCH §7: «Default capture resolution is 1280x720» | in-ticket | — | spec §Покриття → T03 |
| R51 | ARCH §7: «`@on_detect(cls="person")`» — синхронний виклик, без правил і дебаунсу у фазі 1 | in-ticket | — | spec §Покриття → T04 |
| R52 | ARCH §8: «a red crosshair at the centre of the frame, a box around each object, a small green cross at each object's centre, and `dx / dy` printed inside the box» | in-ticket | зв'язано з R04 | spec §Покриття → T05 |
| R53 | ARCH §8: «Labels can be switched off» | in-ticket | — | spec §Покриття → T05 |
| R54 | ARCH §8: вихід — `out\<name>_annotated.jpg` і `out\<name>.json` | in-ticket | — | spec §Покриття → T05 |
| R55 | ARCH §9: схема `config.yaml` — `model{weights,imgsz,conf,conf_debug}`, `classes`, `display{show_labels,show_offsets,crosshair}`, `output{save_json,save_image,dir}`, `capture{width,height}` | in-ticket | — | spec §Покриття → T03 |
| R56 | ARCH §3: «Every tunable number lives in `config.yaml`, never as a constant in code.» | in-ticket | — | spec §Покриття → T03 |
| R57 | ARCH §10: «`bench.py` prints seconds per frame» | in-ticket | — | spec §Покриття → T06 |
| R58 | ARCH §10: «Acceptance is the user's visual judgement — no formal mAP target for this phase.» | in-ticket | приймання оком, не автотестом | spec §Покриття → T06 |

## Як працювати

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R59 | «When you make a technical choice, say in one line why — but do not turn the session into a lecture.» | in-ticket | — | spec §Покриття → T06 |
| R60 | «If something in `ARCHITECTURE.md` turns out to be wrong once code exists, say so and propose the change rather than quietly working around it.» | in-ticket | перше спрацювання: дата релізу YOLO26 в ARCH §3 (spec §Розбіжність) | spec §Покриття → T06 |

## Мається на увазі (в брифі не сказано)

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R61i | *(мається на увазі)* `bus.jpg` у `data/test_images/` має звідкись узятися — а це третє звернення до мережі поверх дозволених двох (R07) | in-ticket | знято брифінгом: качається разом з вагами у фазі 0.5 (див. G03) | spec §Покриття → T02 |
| R62i | *(мається на увазі)* `requirements.txt` і `README.md` є в дереві ARCH §6, але в списку файлів фази 1 їх немає | in-ticket | ремесло, вирішую сам: обидва пишуться, англійською (R21) | spec §Покриття → T01, T06 |
| R63i | *(мається на увазі)* тестів бриф не згадує взагалі; автопілот зазвичай вимагає зелений набір перед комітом | in-ticket | знято брифінгом: мінімальний pytest (див. G02) | spec §Покриття → T03 |
| R64i | *(мається на увазі)* `.gitignore` ховає `data/` — власні фото користувача не потраплять у git | in-ticket | ремесло, вирішую сам: лишаю як у брифі (R35); фото — робочий матеріал, не код | spec §Покриття → T06 |
| R65i | *(мається на увазі)* YOLO26 вийшов у жовтні 2025; версія `ultralytics` з PyPI має його підтримувати, інакше фаза 0.5 не має що качати | in-ticket | перевірено в документації Ultralytics 2026-09-21: моделі `yolo26n.pt`/`yolo26s.pt` існують; на цій машині перевіряє фаза 0.5 | spec §Покриття → T02 |

## Додано користувачем на брифінгу

| ID | Зі слів користувача (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| G01 | «Прапорець у config.yaml, типово вимкнено» — `display.center_line: false`, лінія центр кадру ↔ центр об'єкта | in-ticket | брифінг 2026-09-21, знімає суперечність R04 ↔ ARCH §8 | spec §Покриття → T03, T05 |
| G02 | «Мінімальний pytest»: математика `geometry`, завантаження і валідація `config.yaml`, `FileNotFoundError` у `Detector` без ваг | in-ticket | брифінг 2026-09-21, відповідь на R63i | spec §Покриття → T03, T04 |
| G03 | «Качати разом з вагами у фазі 0.5» — `fetch_models.py` тягне і `bus.jpg` | in-ticket | брифінг 2026-09-21, відповідь на R61i; третє звернення до мережі свідомо злите в той самий одноразовий крок | spec §Покриття → T02 |
