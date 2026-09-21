window.STATE =
{
  "slug": "vision-offline-detector",
  "dir": "2026-09-21-vision-offline-detector--wip",
  "title": "Vision — офлайн-детектор об'єктів (фази 0, 0.5, 1)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-21-brief.md",
  "memoryFile": "CLAUDE.md",
  "skillDir": "C:/Users/asaln/.claude/skills/autopilot",
  "startedAt": "2026-09-21T19:11:37+02:00",
  "updatedAt": "2026-09-21T20:06:22+02:00",
  "finishedAt": null,
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
      "status": "active",
      "startedAt": "2026-09-21T19:43:00+02:00"
    },
    {
      "id": "review",
      "status": "pending"
    },
    {
      "id": "final",
      "status": "pending"
    }
  ],
  "requirements": {
    "total": 68,
    "done": 30,
    "inTicket": 33,
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
      "files": ["requirements.txt", "venv/"],
      "tests": { "passed": 0, "failed": 0 },
      "commit": "e1ce3eb",
      "concerns": ["py -0p друкує 3.11 як -3.1-64 — косметичний баг старого лаунчера"],
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
      "files": ["scripts/fetch_models.py", "models/checksums.txt"],
      "tests": { "passed": 22, "failed": 0 },
      "commit": "8e9ca17",
      "repairFindings": ["один поріг розміру на обидві ваги пропускав обрізаний yolo26s.pt"],
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
      "files": ["core/__init__.py", "core/types.py", "core/config.py", "core/geometry.py", "config.yaml", "tests/"],
      "tests": { "passed": 22, "failed": 0 },
      "commit": "5daff5b",
      "repairFindings": ["тест прибивав значення config.yaml, які користувач має право крутити"],
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
      "status": "in-progress",
      "startedAt": "2026-09-21T20:06:22+02:00",
      "retries": 0,
      "repairs": 0,
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
      "status": "in-progress",
      "startedAt": "2026-09-21T20:06:22+02:00",
      "retries": 0,
      "repairs": 0,
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
      "status": "pending",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    }
  ],
  "singlePass": null,
  "tests": { "passed": 9, "failed": 0 },
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
    "core/config.py:100 — _RANGE_TEXT прив'язує текст до предиката збоку",
    "tests/test_geometry.py:26 — очікуване dx_pct записане тим самим виразом, що й у коді (310/320), а не літералом",
    "tests/test_config.py — після виправлення зник інваріант «whitelist, а не всі 80»: тепер лише isinstance(classes, list)",
    "tests/test_config.py:9 ↔ tests/conftest.py:6 — PROJECT_ROOT визначено двічі"
  ],
  "reviewers": {
    "manifestSpec": "rev-ms-1",
    "craft": "rev-craft-1"
  },
  "blind": null
}
