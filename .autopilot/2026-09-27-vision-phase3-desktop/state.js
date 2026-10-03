window.STATE =
{
  "slug": "vision-phase3-desktop",
  "dir": "2026-09-27-vision-phase3-desktop",
  "title": "Vision — фаза 3: десктопний застосунок (PySide6)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-27-brief.md",
  "memoryFile": "CLAUDE.md",
  "skillDir": "C:/Users/asaln/.claude/skills/autopilot",
  "startedAt": "2026-09-27T17:05:17+02:00",
  "updatedAt": "2026-09-27T21:06:38+02:00",
  "finishedAt": "2026-09-27T21:06:38+02:00",
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-09-27T17:05:17+02:00",
      "finishedAt": "2026-09-27T17:05:40+02:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-09-27T17:05:40+02:00",
      "finishedAt": "2026-09-27T17:06:58+02:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "startedAt": "2026-09-27T17:06:58+02:00",
      "finishedAt": "2026-09-27T17:27:47+02:00",
      "note": "2 питання"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-09-27T17:27:47+02:00",
      "finishedAt": "2026-09-27T17:34:10+02:00"
    },
    {
      "id": "plan",
      "status": "done",
      "startedAt": "2026-09-27T17:34:10+02:00",
      "finishedAt": "2026-09-27T17:37:23+02:00",
      "note": "6 тасків, ярус T2"
    },
    {
      "id": "build",
      "status": "done",
      "startedAt": "2026-09-27T17:37:23+02:00",
      "note": "6 з 6 тасків готові",
      "finishedAt": "2026-09-27T20:59:19+02:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-09-27T17:43:45+02:00",
      "note": "перевірено 6 з 6",
      "finishedAt": "2026-09-27T20:59:19+02:00"
    },
    {
      "id": "final",
      "status": "done",
      "startedAt": "2026-09-27T20:59:19+02:00",
      "finishedAt": "2026-09-27T21:06:38+02:00",
      "note": "сліпе приймання: розбіжностей немає"
    }
  ],
  "requirements": {
    "total": 38,
    "done": 33,
    "inTicket": 0,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 4,
    "dropped": 1
  },
  "tickets": [
    {
      "id": "01",
      "title": "Підготовка core/: ключ кольору, запис конфігу, класи й поріг на льоту",
      "requirements": [
        "R08",
        "R16i",
        "R24",
        "R27",
        "R33",
        "R10.3"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "core/config.py",
        "core/detector.py",
        "core/tracker.py",
        "config.yaml",
        "tests/conftest.py"
      ],
      "status": "done",
      "startedAt": "2026-09-27T17:38:24+02:00",
      "finishedAt": "2026-09-27T17:53:59+02:00",
      "commit": "0bd4a82",
      "tests": {
        "passed": 207,
        "failed": 0
      },
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "_KEY_LINE: quoted value or value with # must parse whole; save over such a line must replace fully or refuse; classes items at any indent; low band test after set_conf"
      ],
      "handoffs": 0
    },
    {
      "id": "02",
      "title": "Спільний конвеєр кадру: core/pipeline.py, detect.py над ним",
      "requirements": [
        "R21",
        "R02",
        "R32",
        "R15i",
        "R19i",
        "R25",
        "R26",
        "R29",
        "R33"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "core/pipeline.py",
        "detect.py"
      ],
      "status": "done",
      "startedAt": "2026-09-27T17:46:12+02:00",
      "finishedAt": "2026-09-27T18:02:55+02:00",
      "commit": "effbcd8",
      "tests": {
        "passed": 243,
        "failed": 0
      },
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "OSError: only write failures map to EXIT_USAGE; photo 'wrote' line order as before; no unused draw import; tests on files, retune display/colour, resplit no mutation"
      ],
      "handoffs": 0
    },
    {
      "id": "05",
      "title": "Панель налаштувань і залежності Qt",
      "requirements": [
        "R08",
        "R16i",
        "R27",
        "R28",
        "R30",
        "R33",
        "R34i"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "requirements.txt",
        "ui/__init__.py",
        "ui/settings_panel.py"
      ],
      "status": "done",
      "startedAt": "2026-09-27T17:46:12+02:00",
      "finishedAt": "2026-09-27T18:00:47+02:00",
      "commit": "765b970",
      "tests": {
        "passed": 215,
        "failed": 0
      },
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "model listed once however weights is spelled; OpenVINO keeps the session imgsz; tests for unknown whitelist class and no changed before editingFinished"
      ],
      "handoffs": 0
    },
    {
      "id": "03",
      "title": "Робітник у фоновому потоці: модель, джерела, стоп, пауза, поріг",
      "requirements": [
        "R05",
        "R06",
        "R10",
        "R13i",
        "R16i",
        "R17i",
        "R18i",
        "R19i",
        "R34i",
        "A01"
      ],
      "blockedBy": [
        "02",
        "05"
      ],
      "wave": 3,
      "zone": [
        "ui/worker.py",
        "core/pipeline.py",
        "core/output.py",
        "core/target.py"
      ],
      "status": "done",
      "startedAt": "2026-09-27T18:02:55+02:00",
      "finishedAt": "2026-09-27T19:18:03+02:00",
      "commit": "32a8e09",
      "tests": {
        "passed": 275,
        "failed": 0
      },
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "redraw must not advance the lost-lock counter; one shared split/colour/target/status/draw method; payload shares no mutable Detection; canvas-copy test able to fail; video end closes source exactly once; failure before first tick closes source + failed; no _LOAD_ERRORS alias; top-level import"
      ],
      "handoffs": 0
    },
    {
      "id": "04",
      "title": "Головне вікно: джерела, перегляд, список об'єктів, повзунок, події",
      "requirements": [
        "R04",
        "R05",
        "R06",
        "R07",
        "R09",
        "R10",
        "R12i",
        "R14i",
        "R15i",
        "R17i",
        "R18i",
        "R23",
        "R26",
        "A01"
      ],
      "blockedBy": [
        "03"
      ],
      "wave": 4,
      "zone": [
        "ui/view.py",
        "ui/main_window.py",
        "app.py"
      ],
      "status": "done",
      "startedAt": "2026-09-27T19:26:37+02:00",
      "finishedAt": "2026-09-27T19:50:36+02:00",
      "commit": "e6886aa",
      "tests": {
        "passed": 302,
        "failed": 0
      },
      "retries": 0,
      "repairs": 2,
      "repairFindings": [
        "flaky stream test (UI starved by frame flood); stale payload after open_source; worker lifetime; ConfigError test; hand-computed click coords; named page step"
      ],
      "handoffs": 0
    },
    {
      "id": "06",
      "title": "Налаштування у вікні, Save to config.yaml, офлайн-доказ, README",
      "requirements": [
        "R01",
        "R03",
        "R08",
        "R16i",
        "R20",
        "R22",
        "R23",
        "R29",
        "R31",
        "R34i"
      ],
      "blockedBy": [
        "04",
        "05"
      ],
      "wave": 5,
      "zone": [
        "ui/main_window.py",
        "README.md",
        "ui/worker.py",
        "app.py"
      ],
      "status": "done",
      "startedAt": "2026-09-27T19:50:36+02:00",
      "finishedAt": "2026-09-27T20:59:19+02:00",
      "commit": "feda87c",
      "tests": {
        "passed": 320,
        "failed": 0
      },
      "retries": 0,
      "repairs": 2,
      "repairFindings": [
        "flaky stream test: worker must not flood the UI (at most one unpainted frame in flight); Save result visible while a stream runs; Save/reload compare the config the panel last sent; one YAML-error sentence; save tests on their own config fixture"
      ],
      "handoffs": 0
    }
  ],
  "singlePass": null,
  "tests": {
    "passed": 320,
    "failed": 0
  },
  "debt": {
    "placeholders": [],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [
    "A01 → R07: пауза/продовження відеофайлу (кнопка і пробіл)"
  ],
  "coverage": {
    "findings": 8,
    "note": "4 missing: ARCH 'rewritten nothing' -> kept as proposal (core/pipeline.py), settings made a live panel without Apply, colour saved via new display.color + save writes only changed values, .exe deferred with reason; 4 half: R29 and R31 got stories, 43 acceptance, 12/40 GUI equivalents"
  },
  "concernsTriage": "Phase 8, 2026-09-27: no fix-now (nothing repeats across 3+ tickets). Dropped: T01 private stub attr (test-only), T01 _check_saved and _key_of (fixed in repair 1). Reported: the other seven.",
  "concerns": [
    "T01 tests/test_detector.py:_classes_sent_to_the_model — reads detector._model.predicted_classes (private attr of the stub)",
    "T01 core/config.py:_check_saved — second classes validation next to _classes() (sent as optional in repair 1)",
    "T01 tests/test_config.py:_key_of — 'everything else unchanged' compares by leaf name, not section key (fixed in repair 1)",
    "T04 ui/main_window.py:287 — on a photo, slider steps by keyboard or wheel also rewrite out\\ files (spec named only release); say so in README",
    "T04 ui/main_window.py:420 — closeEvent waits for the worker thread with no timeout: during the first model load or a hung camera read the window freezes until it finishes (accepted in spec)",
    "T06 ui/main_window.py:unsaved_values — threshold compared in slider hundredths: a file value 0.505 counts as unchanged",
    "T06 photo JSON in out\\ is not written atomically: a reader can see a half-written p0.json while the slider rewrites it (tests tolerate it; out\\ is a debugging surface)",
    "detect.py (phase 2) — load_config lets yaml.YAMLError through, so unparsable config.yaml gives a traceback in detect.py (app.py catches it)",
    "T02 tests/test_pipeline.py:266 — crosshair check reads a hard-coded pixel slice tied to core.draw layout",
    "T05 ui/settings_panel.py:145 — _start_imgsz reset on every set_config, so after a revert the OpenVINO fallback is the reverted imgsz, not the session start"
  ],
  "reviewers": {
    "manifestSpec": "aacfe70a184b96f99",
    "craft": "a825cda1267572a7a"
  },
  "blind": {
    "ran": true,
    "drift": [],
    "notes": [
      "camera:9 error dialog shows, app stays alive, but the view, table and status keep the previous source's picture",
      "offscreen 1280x800 screenshot: image area narrow (~320 px) next to the table — check by eye on a real screen",
      "ARCH §6 'Rewritten: nothing' not kept: core/ gained additions and core/pipeline.py; detect.py rewritten over it (reported as ARCH proposal)",
      "not verified by run: live webcam, click-to-lock on a real camera, {call: on_phone} rule, photo files rewritten on slider release"
    ]
  }
}
