# 07 — Справді офлайн на інференсі, і все англійською

**Вимоги:** R07, R21
**Blocked by:** 06
**Зона:** `core/detector.py`, `core/draw.py`, `core/attributes.py`, `README.md`, `tests/`
**Хвиля:** 5
**Status:** ready

## Що має запрацювати

Сліпе приймання (гейт G4) запустило `detect.py` з перехопленим
`socket.create_connection` і побачило реальну вихідну спробу з'єднання під час
інференсу:

```
('www.google-analytics.com', 443)
ultralytics\utils\events.py:31  _post → urlopen
```

Це телеметрія Ultralytics у фоновому потоці. `SETTINGS['sync']` = `True` у
`C:\Users\asaln\AppData\Roaming\Ultralytics\settings.json`, і в коді проєкту
немає жодного місця, де вона вимикається. Прогін не падає — `_post` ковтає
виняток — але запит іде, і на Pi без мережі він робитиметься щоразу й
відвалюватиметься по таймауту.

Це порушення вимоги, яку бриф називає найважливішою і найлегшою для випадкового
зламу. Вимкнути телеметрію треба **всередині проєкту**, а не правкою
глобального файла налаштувань користувача: репозиторій має бути офлайновим на
будь-якій машині, куди його склонують, включно з Pi.

Друга частина: два коментарі містять українську — `core/draw.py:9` і
`core/attributes.py:6`, обидва `(spec, "Межі та шви")`. І `README.md:173`
містить напівескейплений кириличний приклад
`data\test_images\\u0444ото.jpg` — перший символ екранований, решта ні.

## З брифа, дослівно

> «**Fully offline at runtime.** The network is used exactly twice in the whole
> project: `pip install`, and a one-time weight download. Never at inference
> time. This is the requirement most likely to be broken by accident»
> «Code, comments, logs, README and UI strings | **all English**»

## Розділи специфікації

Історія 20, Рішення §Detector, §логи і тексти.

## Критерії приймання

- [ ] `detect.py` на фото з перехопленим `socket.create_connection` не робить **жодної** вихідної спроби з'єднання. Перевір це так само, як перевіряло приймання, і покажи результат
- [ ] Те саме для `bench.py` і для імпорту `core.detector`
- [ ] Вимкнення живе в коді проєкту і не залежить від глобального `settings.json` користувача — клон на чистій машині офлайновий одразу
- [ ] Глобальний `C:\Users\asaln\AppData\Roaming\Ultralytics\settings.json` **не редагується**: це файл користувача, а не проєкту
- [ ] Тест, який ловить регресію: спроба з'єднання під час інференсу робить його червоним. Модель для цього вантажити не обов'язково, якщо можна перевірити сам механізм вимкнення
- [ ] У `core/draw.py:9` і `core/attributes.py:6` немає української
- [ ] `grep` по `*.py` і `README.md` поза `venv\` не знаходить кирилиці
- [ ] Приклад у `README.md:173` показує те, що справді друкується
- [ ] `pytest -q` зелений (зараз 32 passed)
