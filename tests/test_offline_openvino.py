"""The offline guarantee, OpenVINO half: loading the runtime sends nothing.

`pip install openvino` brings `openvino_telemetry` along, and `import openvino`
imports `openvino.tools.ovc`, which starts a Google Analytics client and posts
an event from a background thread -- consent is assumed when the user profile
holds no consent file. `convert_model` during an export posts more. The
project switches that client off in `core/detector.py`, before the first
`import openvino`, so that OpenVINO falls back to its own no-op stub.

Like `tests/test_offline.py`, this runs in a subprocess: the switch only works
before the first import in a process, and the parent's environment must not be
able to pass the test on the project's behalf.
"""

import json
import os
import subprocess
import sys

from conftest import PROJECT_ROOT

# Sockets are trapped rather than cut, as in test_offline.py. The telemetry
# client is then driven by hand -- a session, an event, a shutdown that waits
# for the sender thread -- so that a live client would be caught in the act
# instead of racing the end of the child process.
CHILD = r"""
import json, socket, sys, time

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
socket.socket.connect = trap("connect", OSError("blocked by test"))

sys.path.insert(0, sys.argv[1])

import core.detector  # noqa: F401 -- importing it first is the thing under test

import openvino
from openvino.tools.ovc import telemetry_utils

telemetry = telemetry_utils.init_ovc_telemetry("vision-test")
telemetry.start_session("ovc")
telemetry.send_event("ovc", "test", "offline")
telemetry_utils.send_conversion_result("success", need_shutdown=True)
time.sleep(1.0)

print(json.dumps({
    "calls": calls,
    "client": telemetry_utils.tm.__name__,
    "loaded": sys.modules.get("openvino_telemetry") is not None,
}))
"""

STUB = "openvino.tools.ovc.telemetry_stub"


def _run_child():
    """Import the detector, then OpenVINO, in a clean process."""
    env = dict(os.environ)
    # OpenVINO's only built-in off switch is "running in CI"; a parent that
    # happens to set one of these must not make the project look offline.
    for name in ("CI", "TF_BUILD", "JENKINS_URL", "PYTEST_CURRENT_TEST"):
        env.pop(name, None)

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


def test_openvino_runs_on_its_no_op_telemetry_stub():
    result = _run_child()

    assert result["client"] == STUB
    assert result["loaded"] is False


def test_loading_openvino_touches_no_socket():
    result = _run_child()

    assert result["calls"] == [], f"network reached by OpenVINO: {result['calls']}"
