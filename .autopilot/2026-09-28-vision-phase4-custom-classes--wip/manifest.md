# Маніфест вимог

Джерело: `2026-09-28-brief.md`. Рядок з цього списку може зняти **тільки користувач**.

Обсяг: фаза 4 (власні класи). Вимоги фаз 0–3 з того самого `PROJECT_PROMPT.md`
закриті попередніми прогонами; сюди перенесені лише ті, що обмежують фазу 4.

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R01 | «працюємо над фазою 4» | in-ticket | — | spec: Історія 1 → T01, T05 |
| R02 | «Only if YOLO26n's stock classes are insufficient — which they are for "pen" and "flower", since neither is in COCO.» | in-ticket | — | spec: Історія 2; реальний результат — Поза рамками (G01) → T05 |
| R03 | «Custom classes (a pen, flowers) are needed later, so the pipeline must support fine-tuning without being restructured.» | in-ticket | — | spec: Історія 3 → T01 |
| R04 | «\| 4 — custom classes \| `training/` \| one config line \|» | in-ticket | — | spec: Історія 3 → T05 |
| R05 | «Method: shoot 10 minutes of video of the object from many angles» | in-ticket | — | spec: Історія 6, 24 → T01 |
| R06 | «take every 20th frame (~900 images with natural variation in angle, blur and lighting)» | in-ticket | — | spec: Історії 6–7 → T01 |
| R07 | «annotate in Label Studio» / «Runs locally via pip. Data never leaves the machine.» | in-ticket | — | spec: Історії 8–9, 31 → T02 |
| R08 | «export in YOLO format» / «Exports YOLO format directly.» | in-ticket | — | spec: Історія 10 → T03 |
| R09 | «fine-tune on Kaggle» / «Free GPU, private datasets, sessions do not drop mid-run.» | in-ticket | — | spec: Історії 17, 20 → T04 |
| R10 | «download `best.pt`» | in-ticket | — | spec: Історія 20; реальний — Поза рамками → T04 |
| R11 | «**Shoot in the conditions the model will actually run in.**» … «a pen lying at an angle on a cluttered desk, 2 metres away, 40 pixels tall, under a yellow lamp» | in-ticket | — | spec: Історія 24 → T05 |
| R12 | «Internet images may be mixed in at around 20% for variety, but the core of the set must be your own frames.» | in-ticket | — | spec: Історія 15 → T03, T05 |
| R13 | «**Include negative frames**: the desk with no pen, the room with no flowers. Without them the model finds pens everywhere.» | in-ticket | — | spec: Історії 11, 24 → T03, T05 |
| R14 | «annotate the first 50 images by hand, train a rough model, let it pre-annotate the remaining 450, then correct its mistakes» | in-ticket | — | spec: Історія 16 → T02, T03 |
| R15 | «Before shooting anything, check whether the class already exists as a labelled dataset (Roboflow Universe, Open Images V7 with 600 classes).» | in-ticket | — | spec: Історія 15 → T03, T05 |
| R16 | «Raw images scraped from a search engine are not — they still have to be annotated by hand» | in-ticket | — | spec: Історія 15; Поза рамками → T03, T05 |
| R17 | «Adding custom classes (phase 4) means **transfer learning**: keep the backbone, replace the head … train on a few hundred custom images» | in-ticket | — | spec: Історія 21 → T04 |
| R18 | «a fine-tuned model sees **only** its new classes. To detect `person` and `pen` together, either include both in the training set, or run two models in sequence.» | in-ticket | брифінг: «include both in the training set», усі 80 класів COCO + нові (G03) | spec: Історія 12; Рішення 1, 9 → T03 |
| R19 | «if phase 4 shows `n` cannot handle them, switching to `s` must not require a network connection» | in-ticket | — | spec: Історія 21 → T04 |
| R20 | «Whether `yolo26n` is accurate enough for a pen. Unknown until I test on my own photos. The fallback path is `yolo26s`, or `imgsz: 960`, or shooting closer.» | in-ticket | — | spec: Історія 23; реальний — Поза рамками → T05 |
| R21 | «**Training must happen in the cloud.** … Training locally on CPU would take 6-10 hours where a GPU takes 15 minutes.» | in-ticket | — | spec: Історія 17 → T04 |
| R22 | «Kaggle (free P100, 30 GPU-hours/week, private datasets) is the chosen provider.» | in-ticket | — | spec: Історія 17 → T04 |
| R23 | «Instance segmentation \| Boxes only. Polygon annotation is 3-5x slower than boxes» | in-ticket | — | spec: Історія 8 → T02 |
| R24 | «**Fully offline at runtime.** … Never at inference time.» / «No runtime network calls, ever.» | in-ticket | — | spec: Історія 25 → T01 |
| R25 | «After this step the project never needs the network again until phase 4.» | in-ticket | — | spec: Історія 25 → T01 |
| R26 | «**Must eventually run on a Raspberry Pi.** The Pi sets the performance budget» / «\| Detector \| **Ultralytics YOLO26n**, one model for every phase \|» | in-ticket | — | spec: Історія 21; Поза рамками → T04 |
| R27 | «**`n`/`s`/`m` are sizes of one model, not different models.** Switching is one config line. Do not build abstraction around "model selection".» | in-ticket | — | spec: Історія 3 → T05 |
| R28 | «**YOLO26 is NMS-free.** … Do not add one» | in-ticket | — | spec: Історія 26 → T02 |
| R29 | «**`core/` must not import from `ui/`** or know how it was launched.» | in-ticket | — | spec: Межі: `core/` не імпортує `training/` (тест) → T01 |
| R30 | «\| Code, comments, logs, README, UI strings \| **all English** \|» | in-ticket | — | spec: Історія 27 → T01 |
| R31 | «Ask before installing anything system-wide.» | in-ticket | — | spec: Історія 8; Рішення 3 → T02 |
| R32 | «Stop after each phase and show me what to run.» | in-ticket | — | spec: Історія 28 → T05 |
| R33 | «I am new to computer vision. When you make a technical choice, say in one line why — but do not turn the session into a lecture.» | in-ticket | — | spec: Історія 27 → T05 |
| R34 | «If something in `ARCHITECTURE.md` turns out to be wrong once code exists, say so and propose the change rather than quietly working around it.» | in-ticket | — | spec: Історія 29 → T05 |
| R35 | «**A pen is a hard class.** Small, thin, low contrast against a desk. May need `imgsz: 960`, or `yolo26s`, or simply shooting from closer.» | in-ticket | — | spec: Історія 23 → T05 |
| R36 | «**Domain gap.** Internet datasets do not match the user's frames. Own footage is mandatory for custom classes.» | in-ticket | — | spec: Історії 15, 24 → T03, T05 |
| R37 | «**Do not skip `conf_debug`.** Recording near-miss detections between 0.25 and 0.5 in the JSON is the main debugging tool for a missed object.» | in-ticket | — | spec: Історія 30 → T05 |
| R38i | *(мається на увазі)* робота фази 4 здебільшого ручна і в користувача (зйомка, розмітка, акаунт і запуск на Kaggle); треба зрозуміти, що саме будує агент, а що — інструкція для користувача | in-ticket | брифінг: вирішено G01 + G02 — зйомка і розмітка за користувачем, усе інше (інструменти, документація, пізніше навчання через CLI) — за агентом | spec: Рішення; G01 + G02 → T05 |
| R39i | *(мається на увазі)* дефолтна модель — OpenVINO (docs/adr/0021); `best.pt` має стати OpenVINO-моделлю тим самим `export_openvino.py` | in-ticket | — | spec: Історія 4 → T04 |
| R40i | *(мається на увазі)* `config.yaml` `classes` і `rules.yaml` (класи правил, `handlers.py`) мають працювати з назвами нових класів | in-ticket | — | spec: Історія 5 → T04 |
| R41i | *(мається на увазі)* датасет потрібно поділити на train/val і описати `data.yaml` для навчання YOLO | in-ticket | — | spec: Історії 13–14 → T03 |
| R42i | *(мається на увазі)* треба спосіб перевірити, чи нова модель достатньо точна (n проти s, `imgsz: 960`) на власних фото | in-ticket | — | spec: Історія 23 → T05 |
| R43i | *(мається на увазі)* мережевих кроків стає більше (Label Studio, Kaggle, готові датасети); правило «мережа лише в `pip install` і `fetch_models.py`» треба розширити так, щоб рантайм лишився офлайн | in-ticket | — | spec: Історія 25; Рішення 10 → T01 |
| G01 | «зроби всю роботу. дай інстукцію, навіть краще - задокументу. Коли я цим вирішу зайнятися - надам всі данні... і ти повчишь можель» | in-ticket | 2026-10-03, відповідь на питання 1: збірка здає весь інструментарій і документацію, перевірені без реальних даних; навчання на реальних даних — пізніше, коли користувач принесе дані, і веде його агент | spec: Історії 1, 32; Поза рамками → T01, T05 |
| G02 | «тоді А» (на «А — через `kaggle` CLI: ключ кладеш сам, я заливаю датасет і ноутбук, запускаю, забираю `best.pt`; кожну заливку — з твого "так"») | in-ticket | 2026-10-03, відповідь на питання 2. Чи є акаунт — не сказано; документація описує, як його завести і підтвердити телефон для GPU | spec: Історії 17–20 → T04, T05 |
| G03 | «просто, навчені обьєкти додай додавай в список» + «так» (на «одна модель на всі 82 класи: частина COCO з Kaggle + твої кадри, люди й телефони на них розмічені поточною моделлю») | in-ticket | 2026-10-03, відповідь на питання 3: нові класи додаються до 80 COCO в одній моделі; список класів у застосунку показує всі; точність COCO-класів міряється, стара модель лишається запасною | spec: Історії 2, 12, 22; Рішення 1, 8 → T01, T03, T04 |

G1 (2026-10-03): брифінг закінчено, три питання. Рядки зі статусом `open` чекають
лише на специфікацію — кожен має відповідь у брифі або в G01–G03, рішення
користувача ніде не бракує.
