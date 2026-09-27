window.STATE =
{
  "slug": "vision-phase2-realtime",
  "dir": "2026-09-22-vision-phase2-realtime",
  "title": "Vision — фаза 2: відео, трекінг, OpenVINO, rules.yaml",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-22-brief.md",
  "memoryFile": "CLAUDE.md",
  "skillDir": "C:/Users/asaln/.claude/skills/autopilot",
  "startedAt": "2026-09-22T22:04:26+02:00",
  "updatedAt": "2026-09-23T01:12:30+02:00",
  "finishedAt": "2026-09-23T01:12:30+02:00",
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-09-22T22:04:26+02:00",
      "finishedAt": "2026-09-22T22:06:10+02:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-09-22T22:06:10+02:00",
      "finishedAt": "2026-09-22T22:14:05+02:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "startedAt": "2026-09-22T22:14:05+02:00",
      "finishedAt": "2026-09-22T22:21:40+02:00"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-09-22T22:21:40+02:00",
      "finishedAt": "2026-09-22T22:42:30+02:00"
    },
    {
      "id": "plan",
      "status": "done",
      "startedAt": "2026-09-22T22:42:30+02:00",
      "finishedAt": "2026-09-22T22:58:20+02:00"
    },
    {
      "id": "build",
      "status": "done",
      "startedAt": "2026-09-22T22:58:20+02:00",
      "note": "7 з 9 тасків готові",
      "finishedAt": "2026-09-23T00:24:30+02:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-09-22T23:01:40+02:00",
      "note": "перевірено 6 з 7, 1 дозапит",
      "finishedAt": "2026-09-23T00:24:30+02:00"
    },
    {
      "id": "final",
      "status": "done",
      "startedAt": "2026-09-23T00:24:30+02:00",
      "note": "сліпе приймання: 0 дрейфів; 2 таски з розбору зауважень",
      "finishedAt": "2026-09-23T01:12:30+02:00"
    }
  ],
  "requirements": {
    "total": 63,
    "done": 58,
    "inTicket": 0,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 4,
    "dropped": 1
  },
  "tickets": [
    {
      "id": "01",
      "title": "Основа: контракт, конфіг, залежності, шина",
      "requirements": [
        "R09",
        "R13",
        "R28",
        "R32",
        "R35i",
        "R41",
        "R49",
        "R53"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "core/types.py",
        "core/config.py",
        "config.yaml",
        "core/events.py",
        "requirements.txt",
        "tests/conftest.py",
        "tests/test_config.py",
        "tests/test_events.py"
      ],
      "status": "done",
      "startedAt": "2026-09-22T22:58:20+02:00",
      "finishedAt": "2026-09-22T23:08:05+02:00",
      "files": [
        "core/types.py",
        "core/config.py",
        "config.yaml",
        "core/events.py",
        "requirements.txt",
        "tests/conftest.py",
        "tests/test_config.py",
        "tests/test_events.py"
      ],
      "tests": {
        "passed": 52,
        "failed": 0
      },
      "commit": "779c9d3",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    },
    {
      "id": "02",
      "title": "Відео і вебкамера в Source",
      "requirements": [
        "R04",
        "R05",
        "R07",
        "R08",
        "R09",
        "R41"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "core/source.py",
        "scripts/grab.py",
        "tests/test_source.py"
      ],
      "status": "done",
      "startedAt": "2026-09-22T23:08:05+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "finishedAt": "2026-09-22T23:31:50+02:00",
      "commit": "d32a725",
      "files": [
        "core/source.py",
        "scripts/grab.py",
        "tests/test_source.py"
      ],
      "tests": {
        "passed": 148,
        "failed": 0
      }
    },
    {
      "id": "03",
      "title": "Трекінг ByteTrack і вибір цілі",
      "requirements": [
        "R10",
        "R11",
        "R12",
        "R15i",
        "R41",
        "R47",
        "R51",
        "R56i"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "core/tracker.py",
        "core/target.py",
        "tests/test_tracker.py",
        "tests/test_target.py",
        "tests/test_offline.py"
      ],
      "status": "done",
      "startedAt": "2026-09-22T23:08:05+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "finishedAt": "2026-09-22T23:31:50+02:00",
      "commit": "2499ded",
      "files": [
        "core/tracker.py",
        "core/target.py",
        "tests/test_tracker.py",
        "tests/test_target.py",
        "tests/test_offline.py"
      ],
      "tests": {
        "passed": 148,
        "failed": 0
      }
    },
    {
      "id": "04",
      "title": "rules.yaml і дебаунс",
      "requirements": [
        "R22",
        "R23",
        "R24",
        "R25",
        "R26",
        "R27",
        "R28",
        "R29",
        "R30",
        "R31",
        "R33",
        "R34i",
        "R35i",
        "R36i",
        "R49",
        "R56i"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "core/rules.py",
        "rules.yaml",
        "tests/test_rules.py"
      ],
      "status": "done",
      "startedAt": "2026-09-22T23:13:30+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "finishedAt": "2026-09-22T23:31:50+02:00",
      "commit": "fd49e24",
      "files": [
        "core/rules.py",
        "rules.yaml",
        "tests/test_rules.py"
      ],
      "tests": {
        "passed": 148,
        "failed": 0
      }
    },
    {
      "id": "05",
      "title": "Експорт в OpenVINO і вимір виграшу",
      "requirements": [
        "R17",
        "R18",
        "R19",
        "R20",
        "R21",
        "R41",
        "R43",
        "R44",
        "R45",
        "R46"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "core/detector.py",
        "scripts/export_openvino.py",
        "bench.py",
        "tests/test_detector.py",
        "tests/test_export.py",
        "tests/test_bench.py"
      ],
      "status": "done",
      "startedAt": "2026-09-22T23:08:05+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 1,
      "finishedAt": "2026-09-23T00:05:20+02:00",
      "commit": "5487d00",
      "files": [
        "core/detector.py",
        "scripts/export_openvino.py",
        "bench.py",
        "requirements.txt",
        ".gitignore",
        "tests/test_detector.py",
        "tests/test_export.py",
        "tests/test_bench.py",
        "tests/test_offline_openvino.py"
      ],
      "tests": {
        "passed": 150,
        "failed": 0
      }
    },
    {
      "id": "06",
      "title": "Вивід потоку і накладка цілі",
      "requirements": [
        "R16i",
        "R26",
        "R27",
        "R36i",
        "R37",
        "R38",
        "R39",
        "R50"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "core/output.py",
        "core/draw.py",
        "tests/test_output.py",
        "tests/test_draw.py"
      ],
      "status": "done",
      "startedAt": "2026-09-22T23:15:10+02:00",
      "retries": 0,
      "repairs": 1,
      "handoffs": 0,
      "repairFindings": [
        "тест «нові аргументи нічого не змінюють» порівнював annotate сам із собою — не міг почервоніти"
      ],
      "finishedAt": "2026-09-22T23:44:10+02:00",
      "commit": "f0a110f",
      "files": [
        "core/output.py",
        "core/draw.py",
        "tests/test_output.py",
        "tests/test_draw.py"
      ],
      "tests": {
        "passed": 149,
        "failed": 0
      }
    },
    {
      "id": "07",
      "title": "Проводка потоку, handlers.py, README",
      "requirements": [
        "R01",
        "R03",
        "R07",
        "R11",
        "R14i",
        "R28",
        "R32",
        "R37",
        "R40i",
        "R42",
        "R48",
        "R50",
        "R52",
        "R54"
      ],
      "blockedBy": [
        "02",
        "03",
        "04",
        "05",
        "06"
      ],
      "wave": 3,
      "zone": [
        "detect.py",
        "handlers.py",
        "README.md",
        "tests/test_detect_cli.py"
      ],
      "status": "done",
      "retries": 1,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-09-23T00:06:10+02:00",
      "finishedAt": "2026-09-23T00:21:10+02:00",
      "commit": "ed254b5",
      "files": [
        "detect.py",
        "handlers.py",
        "README.md",
        "tests/test_detect_cli.py"
      ],
      "tests": {
        "passed": 153,
        "failed": 0
      }
    },
    {
      "id": "08",
      "title": "Камера звільняється завжди, межі модулів цілі",
      "requirements": [
        "R05",
        "R32",
        "R40i",
        "R41",
        "R48"
      ],
      "blockedBy": [
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07"
      ],
      "wave": 4,
      "zone": [
        "core/source.py",
        "detect.py",
        "core/detector.py",
        "core/events.py",
        "tests/test_source.py",
        "tests/test_detect_cli.py",
        "tests/test_bench.py",
        "tests/test_events.py"
      ],
      "status": "done",
      "startedAt": "2026-09-23T00:24:30+02:00",
      "retries": 0,
      "repairs": 1,
      "handoffs": 0,
      "repairFindings": [
        "tests/test_source.py перезбережено з BOM, кириличні імена стали кракозябрами — тест кириличного шляху перестав бути кириличним"
      ],
      "finishedAt": "2026-09-23T00:55:40+02:00",
      "commit": "2f80731",
      "files": [
        "core/source.py",
        "detect.py",
        "core/detector.py",
        "core/events.py",
        "tests/test_source.py",
        "tests/test_detect_cli.py",
        "tests/test_bench.py",
        "tests/test_events.py"
      ],
      "tests": {
        "passed": 188,
        "failed": 0
      }
    },
    {
      "id": "09",
      "title": "Тести беруть значення з конфігу, а не копіюють",
      "requirements": [
        "R49",
        "R56i"
      ],
      "blockedBy": [
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07"
      ],
      "wave": 4,
      "zone": [
        "tests/conftest.py",
        "tests/test_config.py",
        "tests/test_detector.py",
        "tests/test_rules.py",
        "tests/test_target.py",
        "tests/test_tracker.py",
        "tests/test_offline.py",
        "tests/test_types.py"
      ],
      "status": "done",
      "startedAt": "2026-09-23T00:24:30+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "finishedAt": "2026-09-23T00:41:30+02:00",
      "commit": "28e0fd3",
      "files": [
        "tests/conftest.py",
        "tests/test_config.py",
        "tests/test_detector.py",
        "tests/test_rules.py",
        "tests/test_target.py",
        "tests/test_tracker.py",
        "tests/test_offline.py",
        "tests/test_types.py"
      ],
      "tests": {
        "passed": 187,
        "failed": 0
      }
    }
  ],
  "singlePass": null,
  "tests": {
    "passed": 188,
    "failed": 0
  },
  "debt": {
    "placeholders": [],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [],
  "coverage": {
    "ranAt": "2026-09-22T22:41:12+02:00",
    "missing": 0,
    "halfCovered": 6,
    "extra": 14,
    "note": "G2: пропусків немає. Наполовину: emit на потоці, фільтр класу в call, ім'я JSONL камери, трек, що з'явився в зоні, форма target у JSONL, прапорці фази 1 на потоці — усі дописані (історії 40a–42a). Зайве: стартовий рядок консолі прибрано (користувач погодив «лише події»), підсумок лишено як R37.5; «Rewritten: nothing» і нові керувальні типи — додано в пропозиції до ARCHITECTURE.md; решта — R##.n поглиблення, лишено."
  },
  "concerns": [
    "tests/ — немає тесту на значення за замовчуванням Detection.track_id is None і Frame.time == 0.0",
    "tests/test_config.py:37 — тест прибиває значення постаченого config.yaml (30/0.8/true/rules.yaml), які користувач має право крутити",
    "tests/test_config.py:46 — видалення ключа правкою тексту yaml.safe_dump залежить від формату дампу",
    "tests/test_config.py:59 — параметризований тест поганих ключів дублює форму двох наявних тестів",
    "tests/test_events.py:87 — перевірка caplog шукає лише ім'я обробника, а не запис про помилку",
    "requirements.txt:7 — lap і openvino без версій; встановлені 0.5.13 і 2026.4.0 ніде не записані",
    "core/source.py:37 — глушення логів OpenCV на імпорті діє на весь процес; рівень логів мала б ставити точка входу",
    "core/source.py _iter_camera — повторна ітерація камери каже «stopped delivering frames», хоча камеру звільнили ми; немає close() для неітерованого Source",
    "tests/test_source.py:80 — тест кириличного імені не розрізняє, чи спрацював 8.3-шлях, чи довге ім'я",
    "tests/test_source.py:112 — match=\"camera\" надто широкий; розбір camera:N і голого числа без тесту",
    "tests/test_target.py:17, tests/test_tracker.py:24 — TRACK_BUFFER і пороги скопійовані з conftest, а не взяті з cfg",
    "tests/test_offline.py _run_child(script=CHILD, *args) — дефолтний аргумент перед *args",
    "tests/test_rules.py:326 — межа мерехтіння ≤1 замість порожнього списку; немає тесту на present після кулдауну",
    "core/rules.py — повторений switch по rule.when у update і _rule; PROJECT_ROOT і _literal дублюють conftest",
    "OpenVINO: import openvino уже надіслав одну подію телеметрії з цієї машини під час перевірки в таску 01 (файли в %LOCALAPPDATA%\\Intel Corporation) — тепер заблоковано",
    "core/output.py print_event(event: Any) — тест подає SimpleNamespace замість справжнього Event; перейменування поля Event лишить тест зеленим",
    "core/draw.py:26, core/output.py:32 — core.target імпортується лише заради анотації; досить TYPE_CHECKING",
    "core/output.py _open_video — вузький шлях output.dir обробляється інакше, ніж у core/source.py (8.3); два способи на одну пастку",
    "tests/test_output.py — немає тесту на ValueError для canvas іншого розміру і на video=True з save_image: false",
    "core/output.py — загублена заблокована ціль пишеться в JSONL як track_id: null: не видно, який трек був заблокований",
    "tests/test_draw.py — еталонна контрольна сума накладки фото залежить від рендерингу шрифтів OpenCV: оновлення OpenCV може почервонити тест без зміни коду",
    "tests/test_bench.py:35 — випадки \"0\" і \"camera:0\" без пастки на Source: регресія відкриє справжню камеру і зависне замість червоного тесту",
    "core/detector.py sys.modules.setdefault(\"openvino_telemetry\", None) — якщо пакет уже імпортовано раніше, телеметрія мовчки лишиться ввімкненою; варто присвоювати прямо",
    "scripts/export_openvino.py ↔ core/detector.py — «тека з *.xml» і «<stem>_openvino_model» визначені двічі",
    "tests/test_export.py — гілка без openvino (MISSING_OPENVINO_MESSAGE, код 2) без тесту; tests/test_bench.py — відсутні ваги в --weights без тесту",
    "bench.py — середній час на кадр рахується у report і report_speedup двічі; tests/test_detector.py:20 PROJECT_ROOT дублює conftest",
    "core/detector.py KMP_BLOCKTIME=0 — перезаписує значення користувача, а не setdefault; діє на весь процес",
    "tests/test_config.py test_valid_config_exposes_every_value — булеві значення порівнюються через == замість is",
    "tests/test_rules.py — тест present після кулдауну приймає 6.2–6.3 с, хоча результат детермінований 6.2",
    "detect.py _stream — ітератор кадрів закривається перед writer.close(): якщо звільнення захоплення впаде, файли не закриються"
  ],
  "reviewers": {
    "manifestSpec": "aaca60967dbbbf3ec",
    "craft": "a8188b0142b48efa5"
  },
  "blind": {
    "ranAt": "2026-09-23T00:56:00+02:00",
    "drift": [],
    "agreed": 58,
    "note": "Сценарій замовника пройдено запуском: 188 passed; фото bus.jpg — 4 person; відео 190 кадрів → 8 подій, JSONL 190 рядків, mp4 190 кадрів; entered перевірено тимчасовою зоною; call викликав функцію; OpenVINO 1.95x (0.0441 проти 0.0859 с/кадр); camera:9 → код 2; мережевих запитів не зафіксовано. Жива камера, вікно і клік не перевірялись — за користувачем. Побічно: рядок стану в mp4 розмитий (ймовірно mp4v)."
  }
}
