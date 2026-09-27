# 05 — Панель налаштувань (окремий віджет) і залежності Qt

**Вимоги:** R08, R08.1, R08.2, R08.3, R08.4, R16i, R16i.2, R27, R28, R30, R33, R34i
**Blocked by:** 01
**Зона:** `requirements.txt` · `ui/__init__.py` · `ui/settings_panel.py` · `tests/test_ui_settings.py`
**Хвиля:** 2
**Status:** ready

## Що має запрацювати

1. **Залежності.** `PySide6` і `pytest-qt` у `requirements.txt` (коротким коментарем
   «desktop app, phase 3» і «Qt signals in tests»), встановити у venv:
   `venv\Scripts\python -m pip install -r requirements.txt`. Лише venv — нічого системного.
   Якщо встановлення не вдається — `BLOCKED` з точним повідомленням pip.
   `ui/__init__.py` — порожній пакет (однорядковий docstring).
   Offscreen для тестів: `QT_QPA_PLATFORM=offscreen` ставиться до першого імпорту Qt у
   тестах `ui` (наприклад, `os.environ.setdefault` на початку тестового модуля або
   `pytest.ini`/`conftest`-фікстура — `tests/conftest.py` не в зоні цього таска, тож
   краще на рівні модуля тестів).
2. **`ui/settings_panel.py`** — `SettingsPanel(cfg, models_dir)` (QWidget), нічого не знає
   про робітника і вікно; вбудовує його таск 06. Контракт — `interfaces.md`.
   - **Model** — список: `*.pt` і теки `*_openvino_model` у `models_dir`, плюс поточне
     `cfg.model.weights`, навіть якщо його немає на диску. Значення — шлях як у
     `config.yaml` (відносний, прямі слеші).
   - **imgsz** — спінбокс, крок 32; з OpenVINO-моделлю (`OPENVINO_SUFFIX` з
     `core.detector`) неактивний з підказкою «fixed by the export — re-run
     scripts/export_openvino.py --force». Зміна застосовується на `editingFinished`.
   - **Classes** — список із галочками, заповнюється `set_class_names(names: dict[int,
     str])` (з моделі); до виклику — лише поточний whitelist. Жодної галочки = всі класи
     (напис «All classes» під списком).
   - **Colour** (`display.color`), **Centre line** (`display.center_line`) — галочки.
   - **«Save to config.yaml»** — кнопка, сигнал `save_requested()`.
   - Кожна зміна — одразу сигнал `changed(Config)` з новим сеансовим конфігом через
     `dataclasses.replace` (завантажений не мутується).
   - `set_config(cfg)` — повернути віджети до значень (для «модель не завантажилась —
     повернути стару назву»).

## З брифа, дослівно

> «settings» (ARCH §10)
> «`n`/`s`/`m` are sizes of one model, not different models. Switching is one config line.
> Do not build abstraction around "model selection".»
> «Ask before installing anything system-wide.»
> Доповнення: «у панелі модель `.pt`/OpenVINO, список класів, колір, лінія до центру,
> `imgsz`; зміни діють одразу на сеанс»: «"а"»

## Розділи специфікації

Історії 28–35; Рішення: «Стек», «Налаштування — панель, не діалог», «Колір як ключ
конфігу»; Межі та шви — `ui/settings_panel.py`.

## Критерії приймання

- [ ] `PySide6` і `pytest-qt` у `requirements.txt`, встановлені у venv; `import PySide6`
      працює з `venv\Scripts\python`
- [ ] Список моделей у `tmp_path` з `a.pt` і `b_openvino_model/` (з `*.xml`) — обидва
      є; поточна відсутня модель теж показана
- [ ] Зміна кожного віджета дає рівно один `changed(Config)` з потрібним полем; інші поля —
      як були
- [ ] OpenVINO вибрано — `imgsz` неактивний; `.pt` — активний
- [ ] Класи: `set_class_names` заповнює список, галочки відповідають whitelist; зняти всі →
      `classes == []`
- [ ] «Save to config.yaml» → `save_requested`
- [ ] Тести offscreen, без моделі; повний набір тестів зелений
