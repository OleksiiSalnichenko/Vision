# 0013. `openvino` pinned to 2026.3.1 (D02)

## Context

The plan added `openvino` to `requirements.txt` as a CPU runtime. Phase 2 is
about the CPU; OpenVINO on the Intel GPU is explicitly out of scope. The plan
assumed the latest release behaves the same as any other on this laptop, and
that the detector never needs to know which weight format it runs — `YOLO(path)`
picks the backend.

## Decision

The build proved otherwise: `openvino` 2026.4.0 sees this laptop's integrated
GPU, Ultralytics then selects the `AUTO` device, compiles for the iGPU, and the
process dies with access violation `0xC0000005`. `requirements.txt` pins
`openvino==2026.3.1`, which does not see the GPU here, runs on the CPU, and does
not crash.

## Why

The pin removes the crash without the detector learning anything about formats
or devices, and without touching the phase's scope (CPU only).

Considered and rejected:

- **Forcing the device to CPU in the detector.** Would work on any version, but
  gives `Detector` format- and backend-specific code — the one place the design
  keeps free of it — for a device choice the project does not otherwise make.
- **An unpinned or minimum-version requirement.** Installs 2026.4.0 or later
  and crashes on this machine on the first OpenVINO run.
- **Updating the graphics driver or disabling the iGPU.** System changes outside
  the project, and unverifiable from the repository.
- **Investigating the crash to make GPU inference work.** GPU inference is out
  of scope for this phase; the crash is a reason not to be on that path, not a
  task.

## Consequences

This is a workaround by version, not a fix. The pin holds the project on an
older OpenVINO: upgrading `openvino` — or an Ultralytics upgrade that changes how
it picks the OpenVINO device — reopens the crash on this laptop, and the symptom
is a native crash with no Python traceback.

Correctness now depends on a version *not* seeing hardware. On a different
machine whose GPU 2026.3.1 does detect, the same `AUTO` path may be taken; that
case has not been tested. If GPU inference is ever brought into scope, the
device has to become an explicit choice, and this ADR is superseded.
