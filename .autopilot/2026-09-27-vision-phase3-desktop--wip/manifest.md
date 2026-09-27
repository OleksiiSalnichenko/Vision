# Маніфест вимог

Джерело: `2026-09-27-brief.md` (рядок у чаті + дослівний `PROJECT_PROMPT.md` +
дослівні уривки `ARCHITECTURE.md` про фазу 3). `ARCHITECTURE.md` цілком — нормативне
джерело за посиланням із чату. Рядок з цього списку може зняти **тільки користувач**.

Позначки: `i` — мається на увазі, в брифі не сказано прямо. `G` — додано користувачем
після брифа. `D` — відкрито збіркою.

Фази 0, 0.5, 1 і 2 уже збудовані (прогони `2026-09-21-vision-offline-detector`,
`2026-09-22-vision-phase2-realtime`). Вимоги брифа, які стосувались лише їх, тут не
повторюються; ті, що продовжують діяти на фазу 3, перенесені сюди як обмеження.

Після брифінгу (2026-09-27): два питання, обидві відповіді записані (R08/R16i, R15i/R19i).
Решта рядків `open` однозначні і йдуть у специфікацію як є; рядки `R##i` — ремесло, яке
напівавтомат вирішує сам, рішення будуть у `spec.md`. R11 (.exe) відкладено — див. рядок.

## Обсяг

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R01 | «працюємо тільки над фазою 3» | in-ticket | — | spec: уся; Поза рамками → T06 |
| R02 | «на всяк випадок прочита ще файл архітектури - ARCHITECTURE.md» | in-ticket | — | spec: Пропозиції до ARCH → T02 |
| R03 | «Stop after each phase and show me what to run.» | in-ticket | — | spec ІС 46 → T06 |

## Застосунок

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R04 | «PySide6» (ARCH §10), «GUI \| PySide6, phase 3, not before» | in-ticket | — | spec ІС 1 → T04 |
| R05 | «open a file» (ARCH §10) | in-ticket | — | spec ІС 6–8, 15 → T03, 04 |
| R06 | «… or camera» (ARCH §10) | in-ticket | — | spec ІС 10–12 → T03, 04 |
| R07 | «live view» (ARCH §10) | in-ticket | — | spec ІС 9, 16, 19 → T04 |
| R08 | «settings» (ARCH §10) | in-ticket | брифінг 2026-09-27, користувач: «"а"» — у панелі модель `.pt`/OpenVINO, список класів, колір, лінія до центру, `imgsz` | spec ІС 28–35 → T01, 05, 06 |
| R09 | «object list» (ARCH §10) | in-ticket | — | spec ІС 20–22 → T04 |
| R10 | «threshold slider» (ARCH §10) | in-ticket | — | spec ІС 23–27 → T03, 04 |
| R11 | «Real desktop widgets, packageable to .exe.» (ARCH §3) | deferred | «packageable» — властивість вибору PySide6, а не завдання фази 3 (ARCH §10 не називає .exe). Збірка в .exe з torch + OpenVINO — окрема робота (~1–2 ГБ, свої пастки з офлайн-перемикачами); у фазі 3 застосунок запускається з venv. Спека фіксує, що ніщо в `ui/` не заважає збірці пізніше | звіт |
| R12i | *(мається на увазі)* як застосунок запускається — окрема точка входу поряд із `detect.py` | in-ticket | — | spec ІС 1–3 → T04 |
| R13i | *(мається на увазі)* вікно не завмирає, поки модель рахує кадр (0.05–0.08 с на кадр) | in-ticket | — | spec ІС 5; Рішення: потоки → T03 |
| R14i | *(мається на увазі)* що саме показує список об'єктів — «For every detected object the app reports its class, a bounding box, and how far the object's centre sits from the centre of the frame (dx / dy, in pixels and as a fraction of the half-frame).» | in-ticket | — | spec ІС 20 → T04 |
| R15i | *(мається на увазі)* можливості фази 2 у живому перегляді — «Target selection: click an object to lock onto it, otherwise auto-select the one nearest the frame centre.», трекінг, правила з `rules.yaml` | in-ticket | брифінг 2026-09-27, користувач: «ок.. а .. го» — як `detect.py`: трекінг і клік для цілі у живому перегляді, правила спрацьовують, події в панелі «Events» | spec ІС 17, 18, 36–38 → T02, 03, 04 |
| R16i | *(мається на увазі)* куди діваються зміни в налаштуваннях — у `config.yaml` чи лише на сеанс | in-ticket | брифінг 2026-09-27, користувач: «"а"» — зміни діють одразу на сеанс; кнопка «Save to config.yaml» пише змінені значення, коментарі у файлі лишаються | spec ІС 32–34 → T01, 03, 05, 06 |
| R17i | *(мається на увазі)* камера звільняється при зупинці, перемиканні джерела і закритті вікна | in-ticket | — | spec ІС 13 → T03, 04 |
| R18i | *(мається на увазі)* помилки (немає ваг, зайнята камера, битий файл) показуються у вікні, а не валять застосунок | in-ticket | — | spec ІС 4, 11, 12, 14, 35, 38, 40 → T03, 04 |
| R19i | *(мається на увазі)* чи пише застосунок файли в `out\`, як `detect.py` | in-ticket | брифінг 2026-09-27, користувач: «ок.. а .. го» — як `detect.py`: `.jsonl`, кадри подій, `_annotated.mp4` для відеофайлу; для фото `.json` і `_annotated.jpg` | spec ІС 25, 39, 40 → T02, 03 |

## Обмеження, що діють далі

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R20 | «`ui/` imports `core/`, never the reverse.» (ARCH §10), «`core/` must never import from `ui/` or know how it was launched. This is the one structural rule that matters.» (ARCH §6) | in-ticket | — | spec ІС 41; Межі → T06 |
| R21 | «\| 3 — app \| `ui/` (PySide6, imports `core/` as a library) \| nothing \|» (ARCH §6) | in-ticket | — | spec Рішення: конвеєр; Пропозиції до ARCH 1 → T02 |
| R22 | «Fully offline at runtime. The network is used exactly twice in the whole project: `pip install`, and a one-time weight download. Never at inference time.» | in-ticket | — | spec ІС 42 → T06 |
| R23 | «Code, comments, logs, README, UI strings \| all English» | in-ticket | — | spec ІС 43 → T04, 06 |
| R24 | «Every tunable number lives in `config.yaml`, never as a constant in code.» (ARCH §3) | done | — | spec ІС 44 → T01 |
| R25 | «Confidence \| display/events at 0.5; JSON also records everything down to 0.25» | in-ticket | — | spec ІС 27 → T02 |
| R26 | «Do not skip `conf_debug`. Recording near-miss detections between 0.25 and 0.5 in the JSON is the main debugging tool for a missed object.» | in-ticket | — | spec ІС 22 → T02, 04 |
| R27 | «Classes \| whitelist in `config.yaml`, not all 80 COCO classes» | in-ticket | — | spec ІС 30 → T01, 05 |
| R28 | «`n`/`s`/`m` are sizes of one model, not different models. Switching is one config line. Do not build abstraction around "model selection".» | in-ticket | — | spec ІС 29 → T05 |
| R29 | «Must eventually run on a Raspberry Pi. The Pi sets the performance budget, not the laptop.» | in-ticket | — | spec ІС 47 → T02, 06 |
| R30 | «Ask before installing anything system-wide.» | in-ticket | — | spec Рішення: стек → T05 |
| R31 | «When you make a technical choice, say in one line why — but do not turn the session into a lecture.» | in-ticket | — | spec ІС 48 → T06 |
| R32 | «If something in `ARCHITECTURE.md` turns out to be wrong once code exists, say so and propose the change rather than quietly working around it.» | in-ticket | — | spec Пропозиції до ARCH → T02 |
| R33 | «Colour attribute \| in phase 1, but behind a `--color` flag, in its own module» | in-ticket | — | spec ІС 31 → T01, 02, 05 |
| R34i | *(мається на увазі)* UI має тести без моделі, без камери і без живого дисплея — продовження шву з фаз 1–2 | in-ticket | — | spec ІС 45; шви → T03, 05, 06 |

## Додано понад замовлене

| ID | Що | Статус | Підстава | Де |
|----|----|--------|-----------|-----|
| A01 | → R07 («live view»): пауза й продовження відеофайлу (кнопка «Pause»/«Resume», пробіл); на паузі клік і повзунок перемальовують показаний кадр | in-ticket | ідея специфікації: перегляд відео без паузи не дає роздивитися список об'єктів | spec ІС 9 → T03, T04 |

## Відкрито збіркою

| ID | Що довела збірка | Статус | Підстава | Де |
|----|------------------|--------|-----------|-----|
| D01 | Перемалювати кадр на паузі (клік, повзунок) без нового кадру `StreamSession` не вміла; рядок події без друку `core/output.py` не давав | in-ticket | таск 03 повернув BLOCKED: робітник мусив би підміняти глобальний stdout і не міг перемалювати паузу. Додано `StreamSession.redraw()` і `output.format_event`/`format_summary`, зона таска 03 розширена на `core/pipeline.py`, `core/output.py`; ремонт 1 — ще `core/target.py` (`choose(..., new_frame=False)`: перемальовування на паузі не відпускає ціль). Служить A01, R15i, R10 | spec «Межі та шви», поправка D01 → T03 |

## Поза обсягом

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R35 | «Training \| Kaggle notebooks», «Annotation \| Label Studio, local» | deferred | фаза 4, поза обсягом (R01) | звіт |
| R36 | «Export to NCNN (or Hailo if the AI HAT is bought). Web UI on FastAPI» (ARCH §10, фаза 5) | deferred | фаза 5, поза обсягом (R01) | звіт |
| R37 | «One interface over a single image, a folder of images, a video file, a webcam index, and an RTSP URL.» (ARCH §7) — RTSP | deferred | брифінг фази 2, 2026-09-22, користувач: «Відкласти»; ARCH §10 для фази 3 його не називає | звіт |
| R38 | «Deliberately out of scope: Face recognition. Instance segmentation (boxes only). Handwriting OCR. C++. Servo hardware» | dropped | користувач: «Deliberately out of scope» | — |
