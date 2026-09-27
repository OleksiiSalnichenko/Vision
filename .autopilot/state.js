window.STATE =
{
  "slug": "vision-phase3-desktop",
  "dir": "2026-09-27-vision-phase3-desktop--wip",
  "title": "Vision — фаза 3: десктопний застосунок (PySide6)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-27-brief.md",
  "memoryFile": "CLAUDE.md",
  "skillDir": "C:/Users/asaln/.claude/skills/autopilot",
  "startedAt": "2026-09-27T17:05:17+02:00",
  "updatedAt": "2026-09-27T17:38:24+02:00",
  "finishedAt": null,
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-09-27T17:05:17+02:00", "finishedAt": "2026-09-27T17:05:40+02:00" },
    { "id": "manifest",  "status": "done", "startedAt": "2026-09-27T17:05:40+02:00", "finishedAt": "2026-09-27T17:06:58+02:00" },
    { "id": "briefing",  "status": "done", "startedAt": "2026-09-27T17:06:58+02:00", "finishedAt": "2026-09-27T17:27:47+02:00", "note": "2 питання" },
    { "id": "spec",      "status": "done", "startedAt": "2026-09-27T17:27:47+02:00", "finishedAt": "2026-09-27T17:34:10+02:00" },
    { "id": "plan",      "status": "done", "startedAt": "2026-09-27T17:34:10+02:00", "finishedAt": "2026-09-27T17:37:23+02:00", "note": "6 тасків, ярус T2" },
    { "id": "build",     "status": "active", "startedAt": "2026-09-27T17:37:23+02:00", "note": "0 з 6 тасків готові" },
    { "id": "review",    "status": "pending" },
    { "id": "final",     "status": "pending" }
  ],
  "requirements": {
    "total": 38, "done": 0, "inTicket": 33, "inSpec": 0,
    "placeholder": 0, "deferred": 4, "dropped": 1
  },
  "tickets": [
    { "id": "01", "title": "Підготовка core/: ключ кольору, запис конфігу, класи й поріг на льоту", "requirements": ["R08", "R16i", "R24", "R27", "R33", "R10.3"], "blockedBy": [], "wave": 1, "zone": ["core/config.py", "core/detector.py", "core/tracker.py", "config.yaml", "tests/conftest.py"], "status": "in-progress", "startedAt": "2026-09-27T17:38:24+02:00", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "02", "title": "Спільний конвеєр кадру: core/pipeline.py, detect.py над ним", "requirements": ["R21", "R02", "R32", "R15i", "R19i", "R25", "R26", "R29", "R33"], "blockedBy": ["01"], "wave": 2, "zone": ["core/pipeline.py", "detect.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "05", "title": "Панель налаштувань і залежності Qt", "requirements": ["R08", "R16i", "R27", "R28", "R30", "R33", "R34i"], "blockedBy": ["01"], "wave": 2, "zone": ["requirements.txt", "ui/__init__.py", "ui/settings_panel.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "03", "title": "Робітник у фоновому потоці: модель, джерела, стоп, пауза, поріг", "requirements": ["R05", "R06", "R10", "R13i", "R16i", "R17i", "R18i", "R19i", "R34i", "A01"], "blockedBy": ["02", "05"], "wave": 3, "zone": ["ui/worker.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "04", "title": "Головне вікно: джерела, перегляд, список об'єктів, повзунок, події", "requirements": ["R04", "R05", "R06", "R07", "R09", "R10", "R12i", "R14i", "R15i", "R17i", "R18i", "R23", "R26", "A01"], "blockedBy": ["03"], "wave": 4, "zone": ["ui/view.py", "ui/main_window.py", "app.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "06", "title": "Налаштування у вікні, Save to config.yaml, офлайн-доказ, README", "requirements": ["R01", "R03", "R08", "R16i", "R20", "R22", "R23", "R29", "R31", "R34i"], "blockedBy": ["04", "05"], "wave": 5, "zone": ["ui/main_window.py", "README.md"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 }
  ],
  "singlePass": null,
  "tests": null,
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": ["A01 → R07: пауза/продовження відеофайлу (кнопка і пробіл)"],
  "coverage": {
    "findings": 8,
    "note": "4 missing: ARCH 'rewritten nothing' -> kept as proposal (core/pipeline.py), settings made a live panel without Apply, colour saved via new display.color + save writes only changed values, .exe deferred with reason; 4 half: R29 and R31 got stories, 43 acceptance, 12/40 GUI equivalents"
  },
  "concerns": [],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": null
}
