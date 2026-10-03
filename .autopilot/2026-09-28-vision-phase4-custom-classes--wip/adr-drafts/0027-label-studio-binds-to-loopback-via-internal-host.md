# 0027. Label Studio binds to 127.0.0.1 through `--internal-host` (D01)

## Context

The plan assumed that starting Label Studio with `--host 127.0.0.1` keeps it
reachable only from this laptop, so the user's frames, served by Label Studio,
cannot be read from the local network. Task 02 found that in the installed
version `--host` only sets the address written into the URLs Label Studio
generates; the listening socket is chosen by `--internal-host`, which defaults
to `0.0.0.0` — every interface.

## Decision

`training/label_studio.py start` passes `--internal-host 127.0.0.1`. The spec's
story 9 was corrected to say so.

## Why

Considered and rejected:

- **Keeping `--host 127.0.0.1` alone.** The links look local while the server
  answers on the Wi-Fi address too; it breaks "data never leaves the machine"
  silently.
- **Relying on the Windows firewall prompt.** The user may click Allow, and the
  firewall is a system setting the project must not change.
- **Setting the bind address through an environment variable or a settings
  file.** Less visible than a flag on the one command line `start` builds, and
  no more stable across versions.

## Consequences

Label Studio is reachable only from this laptop; labelling from a phone or a
second machine on the same network does not work, by design.

The guarantee rests on a flag name in one Label Studio version. A newer version
that renames or re-purposes `--internal-host` reopens the problem without an
error; a version change in `venv-labelstudio` needs this re-checked.
