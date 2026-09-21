# 01 — Фаза 0: середовище

**Вимоги:** R09, R11, R12, R13, R21, R33, R34, R35, R36, R37, R38, R39, R62i, R33.1
**Blocked by:** —
**Зона:** `venv/`, `requirements.txt`, `.gitignore`, корінь репозиторію
**Хвиля:** 1
**Status:** ready

## Що має запрацювати

На машині з'являється Python 3.11 поруч із системним 3.7.3 — не замість нього і
не в `PATH`. У проєкті з'являється `venv\`, створений саме цим 3.11, з усіма
залежностями. Після цього
`venv\Scripts\python -c "import torch, cv2, ultralytics"` завершується мовчки.

Встановлення Python — системна дія. Спосіб уже погоджений з користувачем:
інсталятор з python.org, ключі `/passive InstallAllUsers=0 PrependPath=0`.
Нічого іншого системного ставити не можна.

Якщо Python 3.11 уже стоїть (`py -0p` його показує) — нічого не ставити,
перейти до venv.

## З брифа, дослівно

> «Install Python 3.11 (alongside 3.7, not on PATH), `git init`, `.gitignore`
> covering `venv/`, `models/*.pt`, `out/`, `data/`, a venv in the project, and
> `ultralytics opencv-python pyyaml numpy scikit-learn`.»
> «Done when `python -c "import torch, cv2, ultralytics"` succeeds.»
> «The machine currently has Python 3.7.3, which is too old — leave it alone»
> «Ask before installing anything system-wide.»

## Розділи специфікації

Історії 1–4, Рішення §Python 3.11, §установка з підтвердженням, §venv,
§requirements.txt.

## Критерії приймання

- [ ] `py -0p` показує і 3.7, і 3.11; `python --version` у звичайній консолі досі 3.7.3
- [ ] `venv\` створений через `py -3.11 -m venv venv`
- [ ] `requirements.txt` містить `ultralytics>=8.4`, `opencv-python`, `pyyaml`, `numpy`, `scikit-learn`, `pytest` — без верхніх меж
- [ ] `venv\Scripts\python -c "import torch, cv2, ultralytics"` завершується з кодом 0
- [ ] `.gitignore` покриває `venv/`, `models/*.pt`, `out/`, `data/`
- [ ] Якщо інсталятор впав — у консолі код повернення і шлях до лога, а не «щось пішло не так»
- [ ] Жодного пакета не поставлено глобально: усе всередині `venv\`
