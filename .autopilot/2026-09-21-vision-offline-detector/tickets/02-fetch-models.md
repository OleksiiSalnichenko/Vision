# 02 — Фаза 0.5: ваги і тестове фото

**Вимоги:** R07, R14, R15, R40, R41, R42, R61i, R65i, G03, R40.1, R40.2, R40.3
**Blocked by:** 01
**Зона:** `scripts/fetch_models.py`, `models/`, `data/test_images/`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

`venv\Scripts\python scripts\fetch_models.py` кладе на диск `models\yolo26n.pt`,
`models\yolo26s.pt` і `data\test_images\bus.jpg`, пише SHA256 у
`models\checksums.txt` і друкує підсумок: ім'я, розмір, сума, статус
(`downloaded` / `skip`).

Це останній раз, коли проєкту потрібна мережа. Після цього запуску все інше має
працювати з вимкненим Wi-Fi.

Повторний запуск нічого не качає, якщо файл на місці і сума збігається.
Обірване завантаження не лишає на диску обрізаний `.pt`, який потім мовчки
зламає детекцію: качати в `<ім'я>.part`, перейменовувати тільки після перевірки.

Ваги резолвити через `ultralytics.utils.downloads.attempt_download_asset` з
явним призначенням у `models\` — тег релізу ассетів рухається, зашитий URL
ламається мовчки. Якщо резолвер не впорався — надрукувати ім'я файлу, теку,
посилання на сторінку релізів Ultralytics і вийти з кодом 1.

## З брифа, дослівно

> «`scripts/fetch_models.py`: download `yolo26n.pt` and `yolo26s.pt` into
> `models\`, write SHA256 sums to `models\checksums.txt`, print a summary.»
> «Fully offline at runtime. The network is used exactly twice in the whole
> project: `pip install`, and a one-time weight download.»
> «`yolo26s.pt`, downloaded but unused, kept for offline availability»

З доповнення брифа (2026-09-21):

> тестове фото: «Качати разом з вагами у фазі 0.5»

## Розділи специфікації

Історії 5–9, Рішення §ваги, §bus.jpg.

## Критерії приймання

- [ ] Після запуску існують `models\yolo26n.pt`, `models\yolo26s.pt`, `data\test_images\bus.jpg`
- [ ] `models\checksums.txt` містить SHA256 обох ваг
- [ ] Підсумок у консолі: ім'я, розмір, сума, статус по кожному файлу
- [ ] Другий запуск друкує `skip` і не звертається до мережі
- [ ] Обірване завантаження лишає по собі нуль файлів `.pt`, а не обрізаний
- [ ] Якщо резолвер не знайшов ваги — точне повідомлення з URL і код виходу 1
- [ ] Жодного іншого місця в проєкті, де код іде в мережу
