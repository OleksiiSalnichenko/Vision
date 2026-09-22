# Маніфест вимог

Джерело: `2026-09-22-brief.md` (рядок у чаті + дослівний `PROJECT_PROMPT.md` +
дослівні уривки `ARCHITECTURE.md` про фазу 2). `ARCHITECTURE.md` цілком — нормативне
джерело за посиланням із чату. Рядок з цього списку може зняти **тільки користувач**.

Позначки: `i` — мається на увазі, в брифі не сказано прямо. `G` — додано користувачем
після брифа. `D` — відкрито збіркою.

Фази 0, 0.5 і 1 уже збудовані (прогін `2026-09-21-vision-offline-detector`). Вимоги
брифа, які стосувались лише їх, тут не повторюються; ті, що продовжують діяти на фазу 2,
перенесені сюди як обмеження.

Після брифінгу (2026-09-22): два питання, обидві відповіді записані (R06, R37). Решта
рядків `open` однозначні і йдуть у специфікацію як є; рядки `R##i` — ремесло, яке
напівавтомат вирішує сам, рішення будуть у `spec.md`.

## Обсяг

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R01 | «працюємо тільки над фазою 2» | in-ticket | — | spec §Покриття → T07 |
| R02 | «на всяк випадок прочита ще файл архітектури - ARCHITECTURE.md» | in-spec | — | spec §Пропозиції до ARCHITECTURE.md → звіт (Phase 8), не таск |
| R03 | «Stop after each phase and show me what to run.» | in-ticket | — | spec §Покриття → T07 |

## Джерело кадрів

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R04 | «Video … branches in `Source`» (ARCH §10) — відеофайл | in-ticket | — | spec §Покриття → T02 |
| R05 | «… and webcam branches in `Source`» (ARCH §10) | in-ticket | — | spec §Покриття → T02 |
| R06 | «One interface over a single image, a folder of images, a video file, a webcam index, and an RTSP URL.» (ARCH §7) | deferred | брифінг 2026-09-22, користувач: «Відкласти» — RTSP поза фазою 2; відео, вебкамера, фото й тека — у фазі 2 | звіт |
| R07 | «Everything downstream is written against the iterator and does not know or care which is in use» (ARCH §7) | in-ticket | — | spec §Покриття → T02, T07 |
| R08 | «Default capture resolution is 1280x720, not 1080p» (ARCH §7) | in-ticket | — | spec §Покриття → T02 |
| R09 | «`source: str  # file path, or "camera:0"`», «`index: int  # 0 for a still image, frame number for video`» (ARCH §7) | in-ticket | — | spec §Покриття → T01, T02 |

## Трекінг і вибір цілі

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R10 | «ByteTrack for stable `track_id` across frames.» (ARCH §10) | in-ticket | — | spec §Покриття → T03 |
| R11 | «Target selection: click an object to lock onto it» (ARCH §10) | in-ticket | — | spec §Покриття → T03, T07 |
| R12 | «otherwise auto-select the one nearest the frame centre.» (ARCH §10) | in-ticket | — | spec §Покриття → T03 |
| R13 | «`Detection` is the only type that crosses module boundaries. Every consumer (drawing, JSON, events, future servo control) reads this and nothing else.» (ARCH §7) | in-ticket | `track_id` мусить дійти до споживачів, а в полях `Detection` його немає — рішення в специфікації | spec §Покриття → T01 |
| R14i | *(мається на увазі)* вибрана ціль і є тим, чиї `dx`/`dy` підуть у `aim(dx, dy)` — «`core/aim.py` exists as a stub taking `aim(dx, dy)`» | in-ticket | — | spec §Покриття → T07 |
| R15i | *(мається на увазі)* що стається, коли заблокована кліком ціль зникла з кадру | in-ticket | — | spec §Покриття → T03 |
| R16i | *(мається на увазі)* вибрана ціль видно відрізняється на накладці | in-ticket | — | spec §Покриття → T06 |

## Прискорення і вимір

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R17 | «Export to OpenVINO» (ARCH §10) | in-ticket | — | spec §Покриття → T05 |
| R18 | «and measure the gain.» (ARCH §10) | in-ticket | — | spec §Покриття → T05 |
| R19 | «OpenVINO (laptop), NCNN or Hailo (Pi) \| Same weights, different export format. One config line.» (ARCH §3) | in-ticket | — | spec §Покриття → T05 |
| R20 | «the rest are estimates to be replaced by real measurements from `bench.py`» — рядок «Laptop, OpenVINO (phase 2) \| ~39 ms \| ~25» (ARCH §4) | in-ticket | — | spec §Покриття → T05 |
| R21 | «Inference runs locally, on CPU, accelerated with OpenVINO (Intel's own runtime, roughly 2-3x faster than plain PyTorch on this hardware).» (ARCH §2) | in-ticket | — | spec §Покриття → T05 |

## Правила і події

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R22 | «`rules.yaml`: conditions (appeared …» (ARCH §10) | in-ticket | — | spec §Покриття → T04 |
| R23 | «… / disappeared …» | in-ticket | — | spec §Покриття → T04 |
| R24 | «… / present for N seconds …» | in-ticket | — | spec §Покриття → T04 |
| R25 | «… / entered a zone)» | in-ticket | — | spec §Покриття → T04 |
| R26 | «actions (log line …» | in-ticket | — | spec §Покриття → T04, T06 |
| R27 | «… save frame …» | in-ticket | — | spec §Покриття → T04, T06 |
| R28 | «… call a function)» | in-ticket | — | spec §Покриття → T01, T04, T07 |
| R29 | «debouncing (confirm over 3 consecutive frames …» | in-ticket | — | spec §Покриття → T04 |
| R30 | «… then 5 seconds cooldown).» | in-ticket | — | spec §Покриття → T04 |
| R31 | «Debouncing is not optional. A model oscillating around the threshold at 0.49/0.51 will otherwise emit hundreds of events in seconds.» | in-ticket | — | spec §Покриття → T04 |
| R32 | «Phase 2 layers rule evaluation and debouncing on top of this same bus without changing its signature.» (ARCH §7) | in-ticket | — | spec §Покриття → T01, T07 |
| R33 | «`rules.yaml` is deferred to phase 2.» | in-ticket | — | spec §Покриття → T04 |
| R34i | *(мається на увазі)* як задається зона для «entered a zone» | in-ticket | — | spec §Покриття → T04 |
| R35i | *(мається на увазі)* як «call a function» у YAML знаходить функцію в Python | in-ticket | — | spec §Покриття → T01, T04 |
| R36i | *(мається на увазі)* куди лягають кадри від «save frame» | in-ticket | — | spec §Покриття → T04, T06 |

## Вивід на відео

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R37 | «Phase 1 output \| OpenCV window + console lines + annotated JPG + JSON» | in-ticket | брифінг 2026-09-22, користувач: «Як ти запропонував» — живе вікно; у консоль лише події з `rules.yaml`; `out/<stem>.jsonl`, рядок на кадр, з near-miss і `track_id`; для відеофайлу ще `out/<stem>_annotated.mp4`, для вебкамери відео не пишеться. Фото — без змін | spec §Покриття → T06, T07 |
| R38 | «Do not skip `conf_debug`. Recording near-miss detections between 0.25 and 0.5 in the JSON is the main debugging tool for a missed object.» | in-ticket | — | spec §Покриття → T06 |
| R39 | «Confidence \| display/events at 0.5; JSON also records everything down to 0.25» | in-ticket | — | spec §Покриття → T06 |
| R40i | *(мається на увазі)* живий показ відео чи вебкамери зупиняється клавішею і не вішає машину | in-ticket | — | spec §Покриття → T07 |

## Обмеження, що діють далі

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R41 | «Fully offline at runtime. The network is used exactly twice in the whole project: `pip install`, and a one-time weight download. Never at inference time.» | in-ticket | — | spec §Покриття → T01, T02, T03, T05 |
| R42 | «Must eventually run on a Raspberry Pi. The Pi sets the performance budget, not the laptop.» | in-ticket | — | spec §Покриття → T07 |
| R43 | «Custom classes (a pen, flowers) are needed later, so the pipeline must support fine-tuning without being restructured.» | in-ticket | — | spec §Покриття → T05 |
| R44 | «Detector \| Ultralytics YOLO26n, one model for every phase» | in-ticket | — | spec §Покриття → T05 |
| R45 | «Ultralytics silently downloads weights. … It must never fall back to the network.» | in-ticket | — | spec §Покриття → T05 |
| R46 | «`n`/`s`/`m` are sizes of one model, not different models. Switching is one config line. Do not build abstraction around "model selection".» | in-ticket | — | spec §Покриття → T05 |
| R47 | «YOLO26 is NMS-free. … Do not add one» | in-ticket | — | spec §Покриття → T03 |
| R48 | «`core/` must not import from `ui/` or know how it was launched.» | in-ticket | — | spec §Покриття → T07 |
| R49 | «Every tunable number lives in `config.yaml`, never as a constant in code.» (ARCH §3) | in-ticket | — | spec §Покриття → T01, T04 |
| R50 | «Code, comments, logs, README, UI strings \| all English» | in-ticket | — | spec §Покриття → T06, T07 |
| R51 | «Classes \| whitelist in `config.yaml`, not all 80 COCO classes» | in-ticket | — | spec §Покриття → T03 |
| R52 | «\| 2 — video \| `core/tracker.py`, `core/rules.py`, a video branch in `source.py` \| nothing \|» (ARCH §6) | in-ticket | — | spec §Покриття → T07 |
| R53 | «Ask before installing anything system-wide.» | in-ticket | — | spec §Покриття → T01 |
| R54 | «When you make a technical choice, say in one line why — but do not turn the session into a lecture.» | in-ticket | — | spec §Покриття → T07 |
| R55 | «If something in `ARCHITECTURE.md` turns out to be wrong once code exists, say so and propose the change rather than quietly working around it.» | in-spec | — | spec §Пропозиції до ARCHITECTURE.md → звіт (Phase 8), не таск |
| R56i | *(мається на увазі)* трекінг, правила й дебаунс мають тести без моделі — продовження шву з фази 1 | in-ticket | — | spec §Покриття → T03, T04 |

## Поза обсягом

| ID | З брифа (дослівно) | Статус | Підстава | Де |
|----|---------------------|--------|-----------|-----|
| R57 | «GUI \| PySide6, phase 3, not before» | deferred | фаза 3, поза обсягом (R01) | звіт |
| R58 | «Training \| Kaggle notebooks», «Annotation \| Label Studio, local» | deferred | фаза 4, поза обсягом (R01) | звіт |
| R59 | «Export to NCNN (or Hailo if the AI HAT is bought). Web UI on FastAPI» (ARCH §10, фаза 5) | deferred | фаза 5, поза обсягом (R01) | звіт |
| R60 | «Deliberately out of scope: Face recognition. Instance segmentation (boxes only). Handwriting OCR. C++. Servo hardware» | dropped | користувач: «Deliberately out of scope» | — |
