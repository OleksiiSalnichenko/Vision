window.STATE =
{
  "slug": "vision-offline-detector",
  "dir": "2026-09-21-vision-offline-detector",
  "title": "Vision — офлайн-детектор об'єктів (фази 0, 0.5, 1)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-21-brief.md",
  "memoryFile": "CLAUDE.md",
  "skillDir": "C:/Users/asaln/.claude/skills/autopilot",
  "startedAt": "2026-09-21T19:11:37+02:00",
  "updatedAt": "2026-09-22T00:42:24+02:00",
  "finishedAt": "2026-09-22T00:42:24+02:00",
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-09-21T19:11:37+02:00",
      "finishedAt": "2026-09-21T19:12:39+02:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-09-21T19:12:39+02:00",
      "finishedAt": "2026-09-21T19:15:57+02:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "startedAt": "2026-09-21T19:15:57+02:00",
      "finishedAt": "2026-09-21T19:30:57+02:00"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-09-21T19:30:57+02:00",
      "finishedAt": "2026-09-21T19:37:33+02:00"
    },
    {
      "id": "plan",
      "status": "done",
      "startedAt": "2026-09-21T19:37:33+02:00",
      "finishedAt": "2026-09-21T19:43:00+02:00"
    },
    {
      "id": "build",
      "status": "done",
      "startedAt": "2026-09-21T19:43:00+02:00",
      "finishedAt": "2026-09-22T00:13:29+02:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-09-21T19:59:06+02:00",
      "finishedAt": "2026-09-22T00:13:29+02:00",
      "note": "6 з 6 тасків перевірено, 4 дозапити"
    },
    {
      "id": "final",
      "status": "done",
      "startedAt": "2026-09-22T00:13:29+02:00",
      "finishedAt": "2026-09-22T00:42:24+02:00",
      "note": "сліпе приймання знайшло 2 дрейфи, обидва закриті"
    }
  ],
  "requirements": {
    "total": 74,
    "done": 69,
    "inTicket": 0,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 4,
    "dropped": 1
  },
  "tickets": [
    {
      "id": "01",
      "title": "Фаза 0: середовище",
      "requirements": [
        "R09",
        "R11",
        "R12",
        "R13",
        "R21",
        "R33",
        "R34",
        "R35",
        "R36",
        "R37",
        "R38",
        "R39",
        "R62i"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "venv/",
        "requirements.txt",
        ".gitignore"
      ],
      "status": "done",
      "startedAt": "2026-09-21T19:45:30+02:00",
      "finishedAt": "2026-09-21T19:52:45+02:00",
      "files": [
        "requirements.txt",
        "venv/"
      ],
      "tests": {
        "passed": 0,
        "failed": 0
      },
      "commit": "e1ce3eb",
      "concerns": [
        "py -0p друкує 3.11 як -3.1-64 — косметичний баг старого лаунчера"
      ],
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    },
    {
      "id": "02",
      "title": "Фаза 0.5: ваги і тестове фото",
      "requirements": [
        "R07",
        "R14",
        "R15",
        "R40",
        "R41",
        "R42",
        "R61i",
        "R65i",
        "G03"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "scripts/fetch_models.py",
        "models/",
        "data/test_images/"
      ],
      "status": "done",
      "finishedAt": "2026-09-21T20:06:22+02:00",
      "files": [
        "scripts/fetch_models.py",
        "models/checksums.txt"
      ],
      "tests": {
        "passed": 22,
        "failed": 0
      },
      "commit": "8e9ca17",
      "repairFindings": [
        "один поріг розміру на обидві ваги пропускав обрізаний yolo26s.pt"
      ],
      "startedAt": "2026-09-21T19:52:45+02:00",
      "retries": 0,
      "repairs": 1,
      "handoffs": 0
    },
    {
      "id": "03",
      "title": "Ядро: типи, конфіг, геометрія",
      "requirements": [
        "R17",
        "R18",
        "R21",
        "R43",
        "R48",
        "R50",
        "R55",
        "R56",
        "R63i",
        "G01",
        "G02"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "core/types.py",
        "core/config.py",
        "core/geometry.py",
        "config.yaml",
        "tests/"
      ],
      "status": "done",
      "finishedAt": "2026-09-21T20:06:22+02:00",
      "files": [
        "core/__init__.py",
        "core/types.py",
        "core/config.py",
        "core/geometry.py",
        "config.yaml",
        "tests/"
      ],
      "tests": {
        "passed": 22,
        "failed": 0
      },
      "commit": "5daff5b",
      "repairFindings": [
        "тест прибивав значення config.yaml, які користувач має право крутити"
      ],
      "startedAt": "2026-09-21T19:52:45+02:00",
      "retries": 0,
      "repairs": 1,
      "handoffs": 0
    },
    {
      "id": "04",
      "title": "Детекція: джерело, детектор, події",
      "requirements": [
        "R02",
        "R03",
        "R08",
        "R10",
        "R16",
        "R26",
        "R28",
        "R29",
        "R30",
        "R31",
        "R32",
        "R49",
        "R51"
      ],
      "blockedBy": [
        "02",
        "03"
      ],
      "wave": 3,
      "zone": [
        "core/source.py",
        "core/detector.py",
        "core/events.py",
        "core/aim.py"
      ],
      "status": "done",
      "finishedAt": "2026-09-21T20:17:05+02:00",
      "files": [
        "core/source.py",
        "core/detector.py",
        "core/events.py",
        "core/aim.py",
        "tests/test_detector.py"
      ],
      "tests": {
        "passed": 24,
        "failed": 0
      },
      "commit": "a945b14",
      "startedAt": "2026-09-21T20:06:22+02:00",
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "реєстр підписок у events.py не очищувався; Detector.is_debug дублював модульний предикат"
      ],
      "handoffs": 0
    },
    {
      "id": "05",
      "title": "Накладка, колір і вивід",
      "requirements": [
        "R04",
        "R19",
        "R20",
        "R52",
        "R53",
        "R54",
        "G01"
      ],
      "blockedBy": [
        "03"
      ],
      "wave": 3,
      "zone": [
        "core/draw.py",
        "core/attributes.py",
        "core/output.py"
      ],
      "status": "done",
      "finishedAt": "2026-09-21T20:18:41+02:00",
      "files": [
        "core/draw.py",
        "core/attributes.py",
        "core/output.py"
      ],
      "tests": {
        "passed": 24,
        "failed": 0
      },
      "commit": "ffe7586",
      "startedAt": "2026-09-21T20:06:22+02:00",
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "центр кадру в draw.py рахувався власним правилом (width // 2) і розходився з geometry; cv2.imwrite падав на не-ANSI шляху"
      ],
      "handoffs": 0
    },
    {
      "id": "06",
      "title": "CLI, вимірювання, README",
      "requirements": [
        "R01",
        "R02",
        "R05",
        "R06",
        "R44",
        "R45",
        "R46",
        "R47",
        "R57",
        "R58",
        "R59",
        "R60",
        "R62i",
        "R64i"
      ],
      "blockedBy": [
        "04",
        "05"
      ],
      "wave": 4,
      "zone": [
        "detect.py",
        "bench.py",
        "scripts/grab.py",
        "README.md"
      ],
      "status": "done",
      "finishedAt": "2026-09-22T00:13:29+02:00",
      "files": [
        "detect.py",
        "bench.py",
        "scripts/grab.py",
        "README.md",
        "config.yaml",
        "core/config.py",
        "tests/test_detect_cli.py"
      ],
      "tests": {
        "passed": 32,
        "failed": 0
      },
      "commit": "3ca6630",
      "startedAt": "2026-09-21T20:18:41+02:00",
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "шапка config.yaml і три обіцянки README не збігалися з кодом; поділ drawn/near-miss не мав жодного твердження в тестах"
      ],
      "handoffs": 0
    }
  ,
    { "id": "07", "title": "Справді офлайн на інференсі, і все англійською", "requirements": ["R07","R21"], "blockedBy": ["06"], "wave": 5, "zone": ["core/detector.py","core/draw.py","core/attributes.py","README.md","tests/"], "status": "done",
      "finishedAt": "2026-09-22T00:37:19+02:00",
      "files": ["core/detector.py", "core/draw.py", "core/attributes.py", "README.md", "tests/test_offline.py"],
      "tests": { "passed": 34, "failed": 0 },
      "commit": "88dd43d", "startedAt": "2026-09-22T00:22:23+02:00", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "08", "title": "Одна схема конфігу в тестах замість чотирьох", "requirements": ["G02","R56"], "blockedBy": ["07"], "wave": 6, "zone": ["tests/"], "status": "done",
      "finishedAt": "2026-09-22T00:42:24+02:00",
      "files": ["tests/conftest.py", "tests/test_config.py", "tests/test_detector.py", "tests/test_detect_cli.py", "tests/test_offline.py"],
      "tests": { "passed": 34, "failed": 0 },
      "commit": "907fbec", "startedAt": "2026-09-22T00:37:19+02:00", "retries": 0, "repairs": 0, "handoffs": 0 }
  ],
  "singlePass": null,
  "tests": {
    "passed": 9,
    "failed": 0
  },
  "debt": {
    "placeholders": [],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [],
  "coverage": {
    "ranAt": "2026-09-21T19:37:33+02:00",
    "missing": 1,
    "halfCovered": 7,
    "extra": 12,
    "note": "G2: пропущено core/__init__.py — додано в Межі та шви. Наполовину: .gitignore, git init, README.md, ~700 рядків, R59, фолбеки yolo26s/imgsz960/зйомка зблизька, відкрите питання про колір — усі дописані. Зайве: Include_launcher=1 прибрано як не з брифа; решта — R##.n поглиблення і ремесло, лишено."
  },
  "concerns": [
    "scripts/fetch_models.py:31 — дві механіки staging для одного інваріанта (тека .part для ваг, суфікс .part для фото); третя ціль додасть третю гілку",
    "scripts/fetch_models.py:23 ↔ config.yaml:5 — тека призначення зашита в скрипті, шлях ваг живе в конфігу: два незалежні факти про одне місце",
    "scripts/fetch_models.py — MIN_BYTES[name] на невідомій цілі дасть сирий KeyError замість FetchError; пороги стоять близько до реального розміру",
    "core/config.py:84 ↔ :24-50 — перелік ключів живе двічі (поля дата-класів і _RULES); поле без правила впаде сирим KeyError",
    "core/attributes.py:134 — недосяжний return \"red\" після циклу: останній бенд накриває весь діапазон hue",
    "core/output.py — стем, що збігається з іменем пристрою Windows (nul, con, com1), не перейменовується: out\\nul.json піде в пристрій",
    "core/output.py — print кириличного імені файлу впаде UnicodeEncodeError на консолі з cp1252",
    "tests/test_detector.py:20 ↔ tests/test_config.py:11 — схема конфігу виписана втретє, хелпер запису продубльований; спільна фікстура в conftest",
    "core/config.py:100 — _RANGE_TEXT прив'язує текст до предиката збоку",
    "tests/test_geometry.py:26 — очікуване dx_pct записане тим самим виразом, що й у коді (310/320), а не літералом",
    "tests/test_config.py — після виправлення зник інваріант «whitelist, а не всі 80»: тепер лише isinstance(classes, list)",
    "tests/test_config.py:9 ↔ tests/conftest.py:6 — PROJECT_ROOT визначено двічі"
  ],
  "reviewers": {
    "manifestSpec": "rev-ms-1",
    "craft": "rev-craft-1"
  },
  "blind": {
    "ranAt": "2026-09-22T00:22:23+02:00",
    "drift": [
      "R07 «fully offline at runtime» — телеметрія Ultralytics робить вихідний запит на www.google-analytics.com:443 під час інференсу (ultralytics/utils/events.py:31). Маніфест казав done, приймання каже частково. Таск 07",
      "R21 «all English» — українська в коментарях core/draw.py:9 і core/attributes.py:6, напівескейплений кириличний приклад у README.md:173. Таск 07"
    ],
    "agreed": 34,
    "note": "Сценарій замовника пройдено від початку до кінця без обривів: 32 passed, detect.py на фото/теці/прапорцях, bench.py 0.0715 s/frame і 13.99 FPS, grab.py зняв реальний кадр 1280x720, обидві помилки з кодом 2, FileNotFoundError без ваг. R45 (~700 рядків) — фактично 1840 рядків коду фази 1."
  }
}
