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
| R01 | «працюємо тальки над фазами 0 - 0.5 - 1» | done | — | T06 · 3ca6630 |
| R02 | «a local, offline object detection application in `D:\Projects\Vision`» | done | — | T06 · 3ca6630 |
| R03 | «For every detected object the app reports its class, a bounding box, and how far the object's centre sits from the centre of the frame (dx / dy, in pixels and as a fraction of the half-frame)» | done | — | T04 · a945b14 |
| R04 | «A crosshair marks the frame centre, a dot marks each object's centre, and a line joins them» | done | суперечність з ARCHITECTURE §8 знята брифінгом: користувач обрав «Прапорець у config.yaml, типово вимкнено» → `display.center_line: false` (див. G01) | T05 · ffe7586 |
| R05 | «Phase 1 works on still images only. Video, tracking and a GUI come later.» | done | — | T06 · 3ca6630 |
| R06 | «Stop after each phase and show me what to run.» | done | — | T06 · 3ca6630 |

## Жорсткі вимоги

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R07 | «Fully offline at runtime. The network is used exactly twice in the whole project: `pip install`, and a one-time weight download. Never at inference time.» | done | 🔴 сліпе приймання G4: телеметрія Ultralytics робить вихідний запит на www.google-analytics.com:443 під час інференсу — маніфест казав done помилково  → виправлено таском 07: YOLO_OFFLINE і YOLO_AUTOINSTALL виставляються до імпорту ultralytics; незалежна перевірка показала 0 спроб з'єднання для detect.py і bench.py | T07 · 88dd43d |
| R08 | «Must eventually run on a Raspberry Pi. The Pi sets the performance budget, not the laptop.» | done | діє як обмеження вибору моделі | T04 · a945b14 |
| R09 | «Personal learning project, not commercial. AGPL-3.0 is fine.» | done | — | T01 · e1ce3eb |
| R10 | «Custom classes (a pen, flowers) are needed later, so the pipeline must support fine-tuning without being restructured.» | done | діє як обмеження структури | T04 · a945b14 |
| R11 | «No NVIDIA GPU, so no CUDA» + «Hardware (already measured, do not re-check)» | done | — | T01 · e1ce3eb |
| R12 | «The machine currently has Python 3.7.3, which is too old — leave it alone and install 3.11 alongside it» | done | — | T01 · e1ce3eb |

## Ухвалені рішення (не переглядаються)

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R13 | «Python 3.11, fresh venv inside the project» | done | — | T01 · e1ce3eb |
| R14 | «**Ultralytics YOLO26n**, one model for every phase» | done | — | T02 · 8e9ca17 |
| R15 | «`yolo26s.pt`, downloaded but unused, kept for offline availability» | done | — | T02 · 8e9ca17 |
| R16 | «display/events at 0.5; JSON also records everything down to 0.25» | done | — | T04 · a945b14 |
| R17 | «`imgsz: 640` (the model's native training size)» | done | — | T03 · 5daff5b |
| R18 | «whitelist in `config.yaml`, not all 80 COCO classes» | done | — | T03 · 5daff5b |
| R19 | «Phase 1 output \| OpenCV window + console lines + annotated JPG + JSON» | done | — | T06 · 3ca6630 |
| R20 | «in phase 1, but behind a `--color` flag, in its own module» | done | — | T05 · ffe7586 |
| R21 | «Code, comments, logs, README, UI strings \| **all English**» | done | 🔴 сліпе приймання G4: українська в коментарях core/draw.py:9 і core/attributes.py:6, кириличний приклад у README.md:173  → виправлено таском 07 | T07 · 88dd43d |
| R22 | «GUI \| PySide6, phase 3, not before» | deferred | поза обсягом цього прогону (R01) | звіт |
| R23 | «Training \| Kaggle notebooks, free GPU» | deferred | фаза 4, поза обсягом (R01) | звіт |
| R24 | «Annotation \| Label Studio, local» | deferred | фаза 4, поза обсягом (R01) | звіт |

## Поза обсягом за словами користувача

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R25 | «Deliberately out of scope: Face recognition. Instance segmentation (boxes only). Handwriting OCR. C++.» | dropped | користувач: «Deliberately out of scope» | — |
| R26 | «Servo hardware — but `core/aim.py` exists as a stub taking `aim(dx, dy)`, so adding real pan-tilt servos later touches one file» | done | саме заглушка в обсязі; реальні сервоприводи — ні | T04 · a945b14 |
| R27 | «`rules.yaml` is deferred to phase 2» | deferred | користувач: «deferred to phase 2» | звіт |

## Пастки, названі користувачем

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R28 | «`config.yaml` stores an explicit path (`models/yolo26n.pt`), and `Detector.__init__` must raise `FileNotFoundError: run scripts/fetch_models.py first` when the file is missing. It must never fall back to the network.» | done | — | T04 · a945b14 |
| R29 | «Switching is one config line. Do not build abstraction around "model selection".» | done | — | T04 · a945b14 |
| R30 | «**YOLO26 is NMS-free.** ... Do not add one; do not port NMS code from YOLO11 examples.» | done | — | T04 · a945b14 |
| R31 | «**`core/` must not import from `ui/`** or know how it was launched.» | done | — | T04 · a945b14 |
| R32 | «Do not skip `conf_debug`. Recording near-miss detections between 0.25 and 0.5 in the JSON» | done | — | T04 · a945b14 |

## Фаза 0 — середовище

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R33 | «Install Python 3.11 (alongside 3.7, not on PATH)» | done | спосіб обрано брифінгом: «Інсталятор з python.org», `/passive InstallAllUsers=0 PrependPath=0` | T01 · e1ce3eb |
| R34 | «`git init`» | done | — | T01 · e1ce3eb |
| R35 | «`.gitignore` covering `venv/`, `models/*.pt`, `out/`, `data/`» | done | — | T01 · e1ce3eb |
| R36 | «a venv in the project» | done | — | T01 · e1ce3eb |
| R37 | «`ultralytics opencv-python pyyaml numpy scikit-learn`» | done | — | T01 · e1ce3eb |
| R38 | «Done when `python -c "import torch, cv2, ultralytics"` succeeds.» | done | — | T01 · e1ce3eb |
| R39 | «Ask before installing anything system-wide.» | done | виконано для Python 3.11 (брифінг 2026-09-21); діє далі на все системне | T01 · e1ce3eb |

## Фаза 0.5 — ваги

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R40 | «`scripts/fetch_models.py`: download `yolo26n.pt` and `yolo26s.pt` into `models\`» | done | — | T02 · 8e9ca17 |
| R41 | «write SHA256 sums to `models\checksums.txt`» | done | — | T02 · 8e9ca17 |
| R42 | «print a summary» | done | — | T02 · 8e9ca17 |

## Фаза 1 — детекція на нерухомих зображеннях

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R43 | «The structure, module contracts, data flow and config schema are specified in sections 6 to 9 of `ARCHITECTURE.md`. Follow them.» | done | — | T03 · 5daff5b |
| R44 | «`detect.py bench.py scripts/{fetch_models,grab}.py core/{types,config,source,detector,geometry,attributes,draw,events,output,aim}.py`» | done | — | T06 · 3ca6630 |
| R45 | «Roughly 700 lines» | done | орієнтир, не мета | T06 · 3ca6630 |
| R46 | «`python detect.py --source data/test_images/bus.jpg`» | done | — | T06 · 3ca6630 |
| R47 | «verify in this order: a stock Ultralytics sample image ... then my own photos ... then the flags, then `scripts/grab.py`» | done | — | T06 · 3ca6630 |
| R48 | ARCH §7: `Detection` з полями `cls_id, cls_name, conf, bbox, center, dx, dy, dx_pct, dy_pct, color`; «`Detection` is the only type that crosses module boundaries» | done | — | T03 · 5daff5b |
| R49 | ARCH §7: «`class Source: def __iter__(self) -> Iterator[Frame]`» — один інтерфейс; «Phase 1 implements the first two» (зображення і тека) | done | — | T04 · a945b14 |
| R50 | ARCH §7: «Default capture resolution is 1280x720» | done | — | T03 · 5daff5b |
| R51 | ARCH §7: «`@on_detect(cls="person")`» — синхронний виклик, без правил і дебаунсу у фазі 1 | done | — | T04 · a945b14 |
| R52 | ARCH §8: «a red crosshair at the centre of the frame, a box around each object, a small green cross at each object's centre, and `dx / dy` printed inside the box» | done | зв'язано з R04 | T05 · ffe7586 |
| R53 | ARCH §8: «Labels can be switched off» | done | — | T05 · ffe7586 |
| R54 | ARCH §8: вихід — `out\<name>_annotated.jpg` і `out\<name>.json` | done | — | T05 · ffe7586 |
| R55 | ARCH §9: схема `config.yaml` — `model{weights,imgsz,conf,conf_debug}`, `classes`, `display{show_labels,show_offsets,crosshair}`, `output{save_json,save_image,dir}`, `capture{width,height}` | done | — | T03 · 5daff5b |
| R56 | ARCH §3: «Every tunable number lives in `config.yaml`, never as a constant in code.» | done | — | T03 · 5daff5b |
| R57 | ARCH §10: «`bench.py` prints seconds per frame» | done | — | T06 · 3ca6630 |
| R58 | ARCH §10: «Acceptance is the user's visual judgement — no formal mAP target for this phase.» | done | приймання оком, не автотестом | T06 · 3ca6630 |

## Як працювати

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R59 | «When you make a technical choice, say in one line why — but do not turn the session into a lecture.» | done | — | T06 · 3ca6630 |
| R60 | «If something in `ARCHITECTURE.md` turns out to be wrong once code exists, say so and propose the change rather than quietly working around it.» | done | перше спрацювання: дата релізу YOLO26 в ARCH §3 (spec §Розбіжність) | T06 · 3ca6630 |

## Мається на увазі (в брифі не сказано)

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R61i | *(мається на увазі)* `bus.jpg` у `data/test_images/` має звідкись узятися — а це третє звернення до мережі поверх дозволених двох (R07) | done | знято брифінгом: качається разом з вагами у фазі 0.5 (див. G03) | T02 · 8e9ca17 |
| R62i | *(мається на увазі)* `requirements.txt` і `README.md` є в дереві ARCH §6, але в списку файлів фази 1 їх немає | done | ремесло, вирішую сам: обидва пишуться, англійською (R21) | spec §Покриття → T01, T06 |
| R63i | *(мається на увазі)* тестів бриф не згадує взагалі; автопілот зазвичай вимагає зелений набір перед комітом | done | знято брифінгом: мінімальний pytest (див. G02) | T03 · 5daff5b |
| R64i | *(мається на увазі)* `.gitignore` ховає `data/` — власні фото користувача не потраплять у git | done | ремесло, вирішую сам: лишаю як у брифі (R35); фото — робочий матеріал, не код | T06 · 3ca6630 |
| R65i | *(мається на увазі)* YOLO26 вийшов у жовтні 2025; версія `ultralytics` з PyPI має його підтримувати, інакше фаза 0.5 не має що качати | done | перевірено в документації Ultralytics 2026-09-21: моделі `yolo26n.pt`/`yolo26s.pt` існують; на цій машині перевіряє фаза 0.5 | T02 · 8e9ca17 |

## Додано користувачем на брифінгу

| ID | Зі слів користувача (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| G01 | «Прапорець у config.yaml, типово вимкнено» — `display.center_line: false`, лінія центр кадру ↔ центр об'єкта | done | ключ у конфігу є (T03 · 5daff5b); малювання лінії — T05 | T05 |
| G02 | «Мінімальний pytest»: математика `geometry`, завантаження і валідація `config.yaml`, `FileNotFoundError` у `Detector` без ваг | done | шви 1–2 зелені (T03 · 5daff5b); шов 3 — T04 | T04 · a945b14 |
| G03 | «Качати разом з вагами у фазі 0.5» — `fetch_models.py` тягне і `bus.jpg` | done | брифінг 2026-09-21, відповідь на R61i; третє звернення до мережі свідомо злите в той самий одноразовий крок | T02 · 8e9ca17 |
| G04 | «я створив репозіторій - git@github.com:OleksiiSalnichenko/Vision.git закоміть будьласка туди в бранчу develop. Як тільки щось буде готово - відразу коміть» | done | сказано в чаті 2026-09-21; `origin` додано, гілка `develop` відгалужена від віддаленої (rebase поверх `e64f54d Create README.md`), пушиться після кожного таска | git remote |

## Відкрито збіркою

| ID | Що показав код | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| D01 | Стейджинг завантаження — тека `models\.part\<ім'я>.pt`, а не файл `<ім'я>.pt.part` | done | резолвер Ultralytics шукає ассет за точним іменем і `yolo26n.pt.part` не знає (таск 02). Служить R40.2; інваріант «у `models\` ніколи не лежить недописаний файл» той самий | spec §історія 8 · T02 · 8e9ca17 |
| D02 | Дефолтів у `core/config.py` немає взагалі: відсутній ключ — `ConfigError`, а не тихе значення за замовчуванням | done | дефолт у модулі — те саме число константою, просто в іншому місці, і це суперечить R56 «every tunable number lives in config.yaml» (таск 03). Спека §config.yaml виправлена | spec §config.yaml · T03 · 5daff5b |
| D04 | Схема `config.yaml` ширша за ARCH §9 на п'ять ключів: `capture.camera`, `capture.count`, `capture.interval`, `bench.runs`, `bench.warmup` | done | точки входу `bench.py` і `grab.py` мають свої дефолти, а дефолт у `argparse` — це та сама константа в коді, яку заборонив R56 і D02 (таск 06). Служить R56 | T06 · 3ca6630 |
| D05 | `--conf` нижче `conf_debug` опускає і `conf_debug` | done | інакше інференс іде з підлогою 0.25 і прапорець мовчки нічого не змінює (таск 06). Побічний ефект: при `--conf` ≤ 0.25 у JSON не лишається жодного `debug: true` — смуга near-miss зникає разом з порогом. Служить R16 і R32, які описують конфіг за замовчуванням | T06 · 3ca6630 |
| D03 | `aim(dx, dy)` повертає рядок-стрілку, а не малює її на кадрі | done | у контракті ARCH §7 `aim(dx, dy)` не має параметра кадру, тож малювати нема на чому (таск 04). Служить R26: точка підключення сервоприводів та сама, один файл. Спека §історія 22 виправлена | spec §історія 22 · T04 |
