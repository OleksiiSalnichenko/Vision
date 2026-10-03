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
  "updatedAt": "2026-10-03T21:40:00+02:00",
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
      "status": "done",
      "startedAt": "2026-10-03T16:44:44+02:00",
      "note": "7 з 7 тасків готові",
      "finishedAt": "2026-10-03T21:40:00+02:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-10-03T16:52:00+02:00",
      "note": "перевірено 7 з 7",
      "finishedAt": "2026-10-03T21:40:00+02:00"
    },
    {
      "id": "final",
      "status": "active",
      "startedAt": "2026-10-03T17:40:43+02:00"
    }
  ],
  "requirements": {
    "total": 46,
    "done": 43,
    "inTicket": 3,
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
      "status": "done",
      "startedAt": "2026-10-03T16:46:10+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "finishedAt": "2026-10-03T16:54:00+02:00",
      "commit": "8330456",
      "tests": {
        "passed": 417,
        "failed": 0
      }
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
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-10-03T16:53:01+02:00",
      "finishedAt": "2026-10-03T17:07:51+02:00",
      "commit": "e7803cc",
      "tests": {
        "passed": 452,
        "failed": 0
      }
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
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-10-03T16:53:01+02:00",
      "finishedAt": "2026-10-03T17:07:52+02:00",
      "commit": "7c5dacf",
      "tests": {
        "passed": 452,
        "failed": 0
      }
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
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-10-03T16:53:01+02:00",
      "finishedAt": "2026-10-03T17:19:09+02:00",
      "commit": "85bed54",
      "tests": {
        "passed": 472,
        "failed": 0
      }
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
      "status": "done",
      "startedAt": "2026-10-03T17:25:06+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "finishedAt": "2026-10-03T17:40:43+02:00",
      "commit": "e139359",
      "tests": {
        "passed": 478,
        "failed": 0
      }
    },
    {
      "id": "06",
      "title": "Виправлення: імена LS, захист даних, помилки одним реченням",
      "requirements": [
        "R07",
        "R08",
        "R12",
        "R14",
        "R24",
        "R42i",
        "G01"
      ],
      "zone": [
        "training/prelabel.py",
        "training/build_dataset.py",
        "training/label_studio.py",
        "training/evaluate.py",
        "training/README.md"
      ],
      "blockedBy": [
        "05"
      ],
      "wave": 4,
      "status": "done",
      "startedAt": "2026-10-03T17:41:56+02:00",
      "retries": 0,
      "repairs": 2,
      "handoffs": 0,
      "finishedAt": "2026-10-03T21:40:00+02:00",
      "commit": "f28503c",
      "tests": {
        "passed": 529,
        "failed": 0
      }
    },
    {
      "id": "07",
      "title": "Виправлення: шлях Kaggle і межа офлайн/мережа",
      "requirements": [
        "R09",
        "R10",
        "R24",
        "R43i",
        "G02"
      ],
      "zone": [
        "training/kaggle_run.py",
        "training/kaggle/"
      ],
      "blockedBy": [
        "05"
      ],
      "wave": 4,
      "status": "done",
      "startedAt": "2026-10-03T17:41:56+02:00",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "finishedAt": "2026-10-03T21:15:13+02:00",
      "commit": "53db001",
      "tests": {
        "passed": 517,
        "failed": 0
      }
    }
  ],
  "singlePass": null,
  "tests": {
    "passed": 529,
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
    "T01 tests/test_training_boundaries.py:12 — imports helpers from tests/test_ui_boundaries.py (test-to-test coupling)",
    "T02 training/prelabel.py:46 — TRAINING_ROOT declared again beside label_studio.TRAINING_ROOT; the LS document root and prelabel's root can drift",
    "T02 training/prelabel.py:107 — _is_labelled matches by '-stem' suffix: a label 'big-pen_000020' marks frame 'pen_000020' of video 'pen' labelled and drops it from tasks.json (correctness)",
    "T02 tests/test_training_prelabel.py — LS id-prefixed names '<id>-stem' / '<id>__stem' are untested",
    "T02 tests/test_training_prelabel.py:119 — conf_debug == model.conf (only confident boxes) is not asserted",
    "T02 training/prelabel.py:38 — offline prelabel imports networked label_studio for two tag names",
    "T02 training/prelabel.py:166 — a model-load error other than OSError/ValueError (e.g. RuntimeError on broken weights) gives a traceback",
    "T02 tests/test_training_label_studio.py:146 — 'start without venv' does not assert TRAINING_ROOT is left uncreated",
    "T03 training/build_dataset.py:77 vs training/prelabel.py:107 — two contradicting parsers of Label Studio export names (8-hex '-' prefix vs any '-'/'__' prefix); '<id>__desk_000020' becomes a one-frame video in build and empties val (cross-ticket Reinvention) — one function in training/ must map an LS name to <video>_<index>",
    "T03 tests/test_training_build.py:236 — ID remap tested only with classes.txt in training.classes order; a naive offset would pass",
    "T03 training/build_dataset.py:297,372 — --name unchecked: '--name .. --force' reaches shutil.rmtree outside build/ and can delete data/training with the user's frames (data loss)",
    "T03 training/build_dataset.py:313 — own frames copied by stem without a collision check; same stem in two subfolders overwrites silently",
    "T03 training/build_dataset.py:361 — a model-load error other than OSError/ValueError gives a traceback",
    "T03 training/build_dataset.py:418 — summary re-reads manifest.json from disk; the 'boxes:' line is untested",
    "T03 tests/test_training_build.py:361 — Cyrillic comment claims the stub read the file; it reads nothing",
    "T04 training/kaggle/train.py:118 — find_dir (Kaggle-only path search, marker with sub-path) has no test; a bug shows only after a push, on the user's GPU hours",
    "T04 tests/test_training_kaggle_run.py — 'kaggle CLI fails -> exit 1' and 'fetch with no best.pt' paths untested",
    "T04 training/kaggle/train.py:166 — check_font no-op proven only because Arial.ttf is not cached here; ticket 05 must repeat it (duplication) — one shared helper with a cache-independent test",
    "T04 training/kaggle_run.py:164 — settings.py splice mismatch raises RuntimeError uncaught in main (traceback)",
    "T04 training/kaggle/train.py:42 — ULTRALYTICS_PIN duplicates requirements.txt pin; no test keeps them equal",
    "T04 training/kaggle/train.py:251 — except (OSError, ValueError, KeyError) around all training hides Ultralytics tracebacks on a failed GPU run",
    "T04 training/kaggle_run.py:123 — any non-zero 'datasets status' read as 'dataset absent'; auth/network failure leads to a confusing create error",
    "T04 training/kaggle_run.py:118 — upload --yes leaves dataset-metadata.json in the user's build folder, outside the interfaces.md format",
    "T05 training/evaluate.py:43 — offline evaluate imports networked training.kaggle.train (NETWORKED list); allowed dependency must be named in test_training_boundaries; train.py must do no network at module level",
    "T05 training/evaluate.py:69 — bad label line (ID outside names, bad number) gives IndexError/ValueError traceback; want one sentence with file+line, exit 2",
    "T05 training/evaluate.py:15 — OpenVINO folder with --imgsz different from export size: RuntimeError not caught, traceback; take size from export or one sentence",
    "T05 training/evaluate.py:99 — each model loaded twice (YOLO + Detector), config.yaml re-read per model",
    "T05 tests/test_training_evaluate.py — refusal \"model knows no class of the build\" untested",
    "T05 tests/test_training_evaluate.py:73 — table parsed by fixed width line[:24]; brittle",
    "T05 training/README.md:107 — Roboflow slugs/licences/counts from search text (403), date of check must be stated",
    "T05 training/README.md:188 — Label Studio click path (local storage, delete tasks) not run; guide does not say so",
    "T05 tests/test_training_e2e.py — prelabel never runs under a socket trap (story 25)",
    "T07 training/kaggle_run.py:52 — 404 rule built on fake CLI output; verify on the first real upload",
    "T07 requirements.txt has ultralytics>=8.4, not a pin; Kaggle pin 8.4.157 tied to the local venv by test",
    "T07 tests/test_training_boundaries.py:30 — a stale ALLOWED_NETWORKED_IMPORTS entry never goes red; \from training import kaggle_run form not caught",
    "T06 training/ls_names.py — with no frames on disk an 8-digit dated clip name reads as an upload prefix; build_dataset warns (first name only)"
  ],
  "reviewers": {
    "manifestSpec": "a9bcbf97b11ed7d7e",
    "craft": "a5ba648952a6eb7a2"
  },
  "blind": null,
  "triage": {
    "fixNow": {
      "06": [
        7,
        8,
        9,
        12,
        14,
        15,
        16,
        17,
        18,
        30,
        31,
        33,
        34,
        35,
        36,
        37
      ],
      "07": [
        11,
        21,
        22,
        24,
        25,
        26,
        27,
        28,
        29
      ]
    },
    "report": [
      0,
      1,
      2,
      3,
      4,
      6,
      10,
      13,
      19,
      20,
      32
    ],
    "drop": {
      "5": "slug verified in T04",
      "23": "shared helper landed in T05"
    }
  }
};
