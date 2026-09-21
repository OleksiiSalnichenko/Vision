"""The offline guarantee: importing the detector must not arm the network.

The brief calls this the requirement most likely to be broken by accident, and
it was: Ultralytics posts anonymous analytics to www.google-analytics.com from
a background thread on every `predict`, and swallows the failure. A run stays
green while the packets leave; on a board with no network it is a five-second
timeout per run instead.

This test does not load a model. It checks the switch, because the switch is
the whole fix: Ultralytics decides once, at import time, whether it is allowed
out, and every later decision reads that frozen answer.

It runs in a subprocess for two reasons. The flag is frozen at the first
`import ultralytics` in the process, so an in-process test would measure
whichever import happened to come first. And Ultralytics turns its own
telemetry off while pytest is running, which would make the assertion green no
matter what the project does.
"""

import json
import os
import subprocess
import sys

from conftest import PROJECT_ROOT

# Sockets are trapped rather than cut: a trap that raised would make
# Ultralytics conclude it is offline for the wrong reason and hide the flag
# under test. `getaddrinfo` answers as a connected machine would.
CHILD = r"""
import json, socket, sys

calls = []


def trap(name, answer):
    def call(*args, **kwargs):
        calls.append(name)
        if isinstance(answer, Exception):
            raise answer
        return answer
    return call


socket.getaddrinfo = trap(
    "getaddrinfo", [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
)
socket.create_connection = trap("create_connection", OSError("blocked by test"))
socket.gethostbyname = trap("gethostbyname", "127.0.0.1")

sys.path.insert(0, sys.argv[1])

import core.detector  # noqa: F401 -- importing it is the thing under test

import ultralytics
import ultralytics.utils

# Answer from a copy of the user's settings that asks for telemetry. The real
# settings.json belongs to the machine, not to this repository, and is left
# untouched: the project has to be offline even on a machine that says sync.
forced = dict(ultralytics.utils.SETTINGS)
forced["sync"] = True
ultralytics.utils.SETTINGS = forced
ultralytics.SETTINGS = forced

from ultralytics.utils.events import events

print(json.dumps({"calls": calls, "telemetry": bool(events.enabled)}))
"""


def _run_child():
    """Import the detector in a clean process and report what it touched."""
    env = dict(os.environ)
    # Both would let the parent's environment pass the test on the project's
    # behalf. The point is that a fresh clone is offline on its own.
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("YOLO_OFFLINE", None)

    done = subprocess.run(
        [sys.executable, "-c", CHILD, str(PROJECT_ROOT)],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, f"child failed:\n{done.stdout}\n{done.stderr}"
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_importing_the_detector_touches_no_socket():
    """Nothing resolves a name or opens a connection on the way in.

    Ultralytics probes DNS at import to decide whether it is online. That probe
    is itself a packet, and it is what tells the telemetry it may send.
    """
    result = _run_child()

    assert result["calls"] == [], f"network reached during import: {result['calls']}"


def test_telemetry_is_disabled_whatever_the_user_settings_say():
    """The analytics POST seen during acceptance can no longer be sent."""
    result = _run_child()

    assert result["telemetry"] is False
