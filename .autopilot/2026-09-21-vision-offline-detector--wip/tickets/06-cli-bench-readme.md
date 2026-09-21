# 06 — CLI, вимірювання, кадри з камери, README

**Вимоги:** R01, R02, R05, R06, R19, R44, R45, R46, R47, R57, R58, R59, R60, R62i, R64i, R02.1, R02.2, R47.1
**Blocked by:** 04, 05
**Зона:** `detect.py`, `bench.py`, `scripts/grab.py`, `README.md`
**Хвиля:** 4
**Status:** ready

## Що має запрацювати

Те, заради чого все попереднє: одна команда на фото — і вікно з накладкою,
файли в `out\`, рядки в консолі.

```
venv\Scripts\python detect.py --source data/test_images/bus.jpg
```

Прапорці: `--color`, `--conf`, `--classes`, `--no-window`. Прапорець перекриває
конфіг; конфіг перекриває дефолти. `--no-window` потрібен, щоб запуск без
графічної сесії не падав на `cv2.imshow` — файли при цьому пишуться як завжди.

`bench.py --source <фото> [--runs N]` друкує секунди на кадр і FPS, з прогрівом
перед вимірюванням (перший прохід завжди повільніший, і без прогріву число
бреше).

`scripts/grab.py [--camera 0] [--count N]` зберігає кадри з вебки в
`data\test_images\`. Роздільність береться з `capture` у конфігу (1280×720).

`README.md` англійською: що це, Install, Run, Config, Troubleshooting. Команди з
нього мають працювати дослівно.

## З брифа, дослівно

> «`python detect.py --source data/test_images/bus.jpg`»
> «Then verify in this order: a stock Ultralytics sample image (proves the
> install), then my own photos (proves the idea), then the flags, then
> `scripts/grab.py` for real frames from my actual webcam.»
> «Roughly 700 lines across: detect.py bench.py scripts/{fetch_models,grab}.py
> core/{...}.py»
> «Done when: dropping in a photo produces a window with boxes, centre dot,
> crosshair and offsets; `out\*.json` contains the numbers; `bench.py` prints
> seconds per frame.»
> «Stop after each phase and show me what to run.»

## Розділи специфікації

Історії 10, 17, 18, 19, 23, 24, 25, 28, 29; Рішення §--no-window, §обсяг фази 1,
§вивід.

## Критерії приймання

- [ ] `detect.py --source <файл>` відкриває вікно, пише JPG і JSON, друкує рядки
- [ ] `detect.py --source <тека>` обходить усі зображення теки
- [ ] `--color`, `--conf`, `--classes`, `--no-window` працюють і перекривають конфіг
- [ ] Неіснуючий файл або не-зображення дає одну англійську фразу зі шляхом і код виходу 2
- [ ] Фото без об'єктів дає `0 detections`, порожній масив у JSON і кадр із самим перехрестям
- [ ] `bench.py` друкує секунди на кадр і FPS, з прогрівом
- [ ] `grab.py` зберігає кадри в `data\test_images\`; зайнята або відсутня камера — одна фраза і код виходу 2
- [ ] `README.md` англійською, з розділами Install / Run / Config / Troubleshooting; команди з нього працюють дослівно
- [ ] `pytest -q` зелений
- [ ] `git status` чистий після запуску (нічого з `out\`, `models\`, `data\` не просочилось)
