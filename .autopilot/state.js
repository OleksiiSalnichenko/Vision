window.STATE =
{
  "slug": "vision-phase2-realtime",
  "dir": "2026-09-22-vision-phase2-realtime--wip",
  "title": "Vision — фаза 2: відео, трекінг, OpenVINO, rules.yaml",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-22-brief.md",
  "memoryFile": "CLAUDE.md",
  "skillDir": "C:/Users/asaln/.claude/skills/autopilot",
  "startedAt": "2026-09-22T22:04:26+02:00",
  "updatedAt": "2026-09-22T22:42:30+02:00",
  "finishedAt": null,
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
      "status": "active",
      "startedAt": "2026-09-22T22:14:05+02:00"
    },
    {
      "id": "spec",
      "status": "active",
      "startedAt": "2026-09-22T22:21:40+02:00"
    },
    {
      "id": "plan",
      "status": "active",
      "startedAt": "2026-09-22T22:42:30+02:00"
    },
    {
      "id": "build",
      "status": "pending"
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
    "total": 60,
    "done": 0,
    "inTicket": 53,
    "inSpec": 2,
    "placeholder": 0,
    "deferred": 4,
    "dropped": 1
  },
  "tickets": [
    { "id": "01", "title": "Основа: контракт, конфіг, залежності, шина", "requirements": ["R09","R13","R28","R32","R35i","R41","R49","R53"], "blockedBy": [], "wave": 1, "zone": ["core/types.py","core/config.py","config.yaml","core/events.py","requirements.txt","tests/conftest.py","tests/test_config.py","tests/test_events.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "02", "title": "Відео і вебкамера в Source", "requirements": ["R04","R05","R07","R08","R09","R41"], "blockedBy": ["01"], "wave": 2, "zone": ["core/source.py","scripts/grab.py","tests/test_source.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "03", "title": "Трекінг ByteTrack і вибір цілі", "requirements": ["R10","R11","R12","R15i","R41","R47","R51","R56i"], "blockedBy": ["01"], "wave": 2, "zone": ["core/tracker.py","core/target.py","tests/test_tracker.py","tests/test_target.py","tests/test_offline.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "04", "title": "rules.yaml і дебаунс", "requirements": ["R22","R23","R24","R25","R26","R27","R28","R29","R30","R31","R33","R34i","R35i","R36i","R49","R56i"], "blockedBy": ["01"], "wave": 2, "zone": ["core/rules.py","rules.yaml","tests/test_rules.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "05", "title": "Експорт в OpenVINO і вимір виграшу", "requirements": ["R17","R18","R19","R20","R21","R41","R43","R44","R45","R46"], "blockedBy": ["01"], "wave": 2, "zone": ["core/detector.py","scripts/export_openvino.py","bench.py","tests/test_detector.py","tests/test_export.py","tests/test_bench.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "06", "title": "Вивід потоку і накладка цілі", "requirements": ["R16i","R26","R27","R36i","R37","R38","R39","R50"], "blockedBy": ["01"], "wave": 2, "zone": ["core/output.py","core/draw.py","tests/test_output.py","tests/test_draw.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "07", "title": "Проводка потоку, handlers.py, README", "requirements": ["R01","R03","R07","R11","R14i","R28","R32","R37","R40i","R42","R48","R50","R52","R54"], "blockedBy": ["02","03","04","05","06"], "wave": 3, "zone": ["detect.py","handlers.py","README.md","tests/test_detect_cli.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 }
  ],
  "singlePass": null,
  "tests": null,
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
  "concerns": [],
  "reviewers": {
    "manifestSpec": null,
    "craft": null
  },
  "blind": null
}
