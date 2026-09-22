# 0012. OpenVINO telemetry blocked in-process (D01)

## Context

The project is fully offline at runtime: the network is used for `pip install`
and the one-time weight download, never at inference time. The plan covered
Ultralytics' own network behaviour (`YOLO_OFFLINE`, `YOLO_AUTOINSTALL=0`) and
assumed that adding `openvino` to `requirements.txt` added a runtime and nothing
else.

## Decision

The build proved otherwise: `import openvino` itself sends an event to Google
Analytics through its dependency `openvino-telemetry`, which is opt-out. One
event from this machine had already gone out while verifying the installation
in task 01.

`core/detector.py` sets `sys.modules["openvino_telemetry"] = None` before the
first import of `openvino`, so the telemetry package cannot be imported and
OpenVINO runs without it. A subprocess test in `tests/test_offline.py` loads the
OpenVINO path in a clean process and asserts no socket is opened.

## Why

The block has to live in the same place, and be subject to the same import-order
discipline, as the Ultralytics switches: the process is offline only if the
first module to touch the stack closes every door before it does.

Considered and rejected:

- **The package's own opt-out.** It records consent per user profile, outside
  the project: a fresh machine, a new user account or a reset profile starts
  sending again, and nothing in the repository shows whether it is in effect.
- **Uninstalling `openvino-telemetry`.** It is a declared dependency of
  `openvino`; the next `pip install -r requirements.txt` puts it back.
- **A firewall rule.** A system setting outside the project, and outside what
  the project is allowed to change.
- **Documenting it and accepting the traffic.** Contradicts the offline
  requirement outright.

## Consequences

The block depends on import order, like the rest of the offline invariant: any
module that imports `openvino` before `core.detector` has run reopens the leak,
and in-process tests would not notice. Only the subprocess test guards it.

`sys.modules[...] = None` relies on OpenVINO tolerating a missing telemetry
module. A future `openvino` release that imports it unconditionally would fail
at import time — loud, which is the acceptable failure mode here.

The one event already sent cannot be recalled; it is recorded so the claim
"never used the network" is not made for this machine.
