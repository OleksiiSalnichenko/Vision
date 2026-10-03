window.STATE =
{
  "slug": "vision-phase4-custom-classes",
  "dir": "2026-09-28-vision-phase4-custom-classes--wip",
  "title": "Vision — фаза 4: власні класи (ручка, квіти)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-28-brief.md",
  "memoryFile": "CLAUDE.md",
  "skillDir": "C:/Users/asaln/.claude/skills/autopilot",
  "startedAt": "2026-09-28T23:46:32+02:00",
  "updatedAt": "2026-10-03T16:53:01+02:00",
  "finishedAt": null,
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-09-28T23:46:32+02:00",
      "finishedAt": "2026-09-28T23:58:40+02:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-09-28T23:49:10+02:00",
      "finishedAt": "2026-09-28T23:58:40+02:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "startedAt": "2026-09-28T23:58:40+02:00",
      "finishedAt": "2026-10-03T16:38:17+02:00",
      "note": "3 питання"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-10-03T16:38:17+02:00",
      "finishedAt": "2026-10-03T16:41:30+02:00"
    },
    {
      "id": "plan",
      "status": "done",
      "startedAt": "2026-10-03T16:41:30+02:00",
      "finishedAt": "2026-10-03T16:44:44+02:00",
      "note": "5 тасків, ярус T2"
    },
    {
      "id": "build",
      "status": "active",
      "startedAt": "2026-10-03T16:44:44+02:00",
      "note": "0 з 5 тасків готові"
    },
    {
      "id": "review",
      "status": "active",
      "startedAt": "2026-10-03T16:52:00+02:00",
      "note": "перевіряю 01"
    },
    {
      "id": "final",
      "status": "pending"
    }
  ],
  "requirements": {
    "total": 46,
    "done": 0,
    "inTicket": 46,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 0,
    "dropped": 0
  },
  "tickets": [
    {
      "id": "01",
      "title": "Основа training/: конфіг, класи, кадри з відео",
      "requirements": [
        "R01",
        "R03",
        "R05",
        "R06",
        "R24",
        "R25",
        "R29",
        "R30",
        "R43i",
        "G01",
        "G03"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "training/settings.py",
        "training/classes.py",
        "training/extract_frames.py",
        "training/training.yaml"
      ],
      "status": "review",
      "startedAt": "2026-10-03T16:46:10+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    },
    {
      "id": "02",
      "title": "Label Studio: установка, запуск, авторозмітка",
      "requirements": [
        "R07",
        "R14",
        "R23",
        "R31",
        "R28"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "training/label_studio.py",
        "training/prelabel.py"
      ],
      "status": "in-progress",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-10-03T16:53:01+02:00"
    },
    {
      "id": "03",
      "title": "Збирач датасету",
      "requirements": [
        "R08",
        "R12",
        "R13",
        "R15",
        "R16",
        "R18",
        "R36",
        "R41i",
        "G03",
        "R14"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "training/build_dataset.py"
      ],
      "status": "in-progress",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-10-03T16:53:01+02:00"
    },
    {
      "id": "04",
      "title": "Навчання на Kaggle і smoke-прогін",
      "requirements": [
        "R09",
        "R10",
        "R17",
        "R19",
        "R21",
        "R22",
        "R26",
        "R39i",
        "R40i",
        "G02",
        "G03"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "training/kaggle_run.py",
        "training/kaggle/"
      ],
      "status": "in-progress",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-10-03T16:53:01+02:00"
    },
    {
      "id": "05",
      "title": "Порівняння моделей і посібник",
      "requirements": [
        "R01",
        "R02",
        "R04",
        "R11",
        "R12",
        "R13",
        "R15",
        "R16",
        "R20",
        "R27",
        "R32",
        "R33",
        "R34",
        "R35",
        "R36",
        "R37",
        "R42i",
        "R38i",
        "G01",
        "G02"
      ],
      "blockedBy": [
        "02",
        "03",
        "04"
      ],
      "wave": 3,
      "zone": [
        "training/evaluate.py",
        "training/README.md",
        "README.md"
      ],
      "status": "pending",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    }
  ],
  "singlePass": null,
  "tests": {
    "passed": 324,
    "failed": 0
  },
  "debt": {
    "placeholders": [
      "G02 — training.kaggle.username: логін Kaggle"
    ],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [],
  "coverage": {
    "findings": 5,
    "note": "0 missing, 5 half: rough dataset mode (story 16 now defines build_dataset --rough), Open Images not YOLO (FiftyOne commands in the guide), ~20% now of the whole set, LS analytics made concrete, COCO slug named with verify step; additions are deepening of R/G rows, kept"
  },
  "concerns": [
    "T01 training/extract_frames.py:52 — Source(video, None) relies on the video branch never reading cfg; a change in core.source breaks it silently",
    "T01 training/extract_frames.py:48,93 — 'video not found' sentence built in two places",
    "T01 training/extract_frames.py:108 — with --out outside FRAMES_ROOT the 'total' line ignores the frames just written; untested",
    "T01 tests/test_training_frames.py:88 — Cyrillic test skips itself on a volume without 8.3 names; a skip reads as green",
    "T01 tests/test_training_settings.py:229 — 'every key commented' check accepts a comment on the previous line belonging to another key",
    "T01 training/training.yaml:41 — coco_dataset slug not verified yet (ticket 04 verifies)",
    "T01 tests/test_training_boundaries.py:12 — imports helpers from tests/test_ui_boundaries.py (test-to-test coupling)"
  ],
  "reviewers": {
    "manifestSpec": "a9bcbf97b11ed7d7e",
    "craft": "a5ba648952a6eb7a2"
  },
  "blind": null
}
