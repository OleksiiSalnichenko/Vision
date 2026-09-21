# 0002. Download staging directory (D01)

## Context

The plan required that an interrupted download never leave a truncated weight
file in `models\`, and assumed the usual shape for that: a sibling file named
`<name>.pt.part`, renamed once complete.

## Decision

Downloads stage into a service directory, `models\.part\<name>.pt`, keeping the
asset's exact filename. The file moves into `models\` only after its size is
verified; anything left in `.part` is cleaned up.

## Why

Building it showed the suffix does not survive contact with the downloader. The
Ultralytics resolver (`attempt_download_asset`) resolves and writes by the exact
asset name; `yolo26n.pt.part` is a name it does not know, so the suffix form
fights the very component that finds the weights. Staging by directory keeps the
filename intact and still keeps the incomplete file out of `models\`.

Considered and rejected:

- **`<name>.pt.part` sibling file.** The resolver will not produce or accept the
  renamed asset, so the script would have to bypass the resolver and hard-code a
  URL — the thing 0.5 deliberately avoids.
- **Download straight into `models\` and delete on failure.** The failures that
  matter are the ones where cleanup never runs: a killed process, a dropped
  connection, a reboot. A truncated `yolo26n.pt` then survives and breaks
  detection much later, silently.

## Consequences

`models\` now contains a subdirectory that is not weights. Anything listing
`models\` — future scripts, checksum reporting, cleanup — must skip it, and a
crash can leave a partial file sitting there until the next run sweeps it.

There is no resume: an interrupted download is discarded and refetched whole,
which costs the full file again on a bad connection. The guarantee bought is
narrow but exact — `models\` never holds a file that is not complete.
