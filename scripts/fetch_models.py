#!/usr/bin/env python
"""One-time online step: fetch the YOLO26 weights and the stock test image.

This is the only module in the project that is allowed to touch the network.
Once it has run, everything else works with the Wi-Fi turned off.

Usage:
    venv\\Scripts\\python scripts\\fetch_models.py

Re-running is cheap: a file that is already on disk with a matching SHA256 is
reported as "skip" and the network is not touched at all -- the Ultralytics
downloader is imported lazily, inside the download helpers.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
IMAGES_DIR = PROJECT_ROOT / "data" / "test_images"
CHECKSUMS_FILE = MODELS_DIR / "checksums.txt"

# Weights are staged inside a directory instead of under a "<name>.part" file
# because the Ultralytics resolver looks an asset up by its exact filename:
# "yolo26n.pt.part" is not an asset it knows. The rule the staging keeps is the
# one that matters -- the final path never holds a half-written file.
STAGING_DIR = MODELS_DIR / ".part"
IMAGE_PART_SUFFIX = ".part"

WEIGHT_NAMES = ("yolo26n.pt", "yolo26s.pt")
TEST_IMAGE_NAME = "bus.jpg"
TEST_IMAGE_URL = "https://ultralytics.com/images/bus.jpg"
ASSET_RELEASES_PAGE = "https://github.com/ultralytics/assets/releases"

# Size floor per target, not one floor for all of them: a single floor low
# enough for yolo26n.pt (~5.3 MiB) lets a transfer that died at 2 MiB pass for
# yolo26s.pt (~19.5 MiB). Each value sits just under the real size of that file.
MIN_BYTES = {
    "yolo26n.pt": 5_000_000,
    "yolo26s.pt": 19_000_000,
    TEST_IMAGE_NAME: 120_000,
}

# A .pt written by torch.save is a zip container, and a truncated one has lost
# its central directory. This catches the abort at 99% that a size floor cannot.
ZIP_CONTAINER_TARGETS = frozenset(WEIGHT_NAMES)

# safe_download's own floor for the test image; it aborts the transfer early.
MIN_IMAGE_BYTES = 10_000

SHA256_CHUNK_BYTES = 1024 * 1024


class FetchError(Exception):
    """A target could not be downloaded; the message tells the user what to do."""


def _rel(path: Path) -> str:
    """Path relative to the project root, with forward slashes."""
    return path.relative_to(PROJECT_ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(SHA256_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _human_size(size: int) -> str:
    mib = size / (1024 * 1024)
    if mib >= 1:
        return f"{mib:.1f} MiB"
    return f"{size / 1024:.1f} KiB"


def _read_checksums() -> dict[str, str]:
    """Read "<sha256>  <path>" lines written by an earlier run."""
    if not CHECKSUMS_FILE.is_file():
        return {}
    sums: dict[str, str] = {}
    for line in CHECKSUMS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1]] = parts[0]
    return sums


def _write_checksums(sums: dict[str, str]) -> None:
    lines = [f"{sums[name]}  {name}" for name in sorted(sums)]
    CHECKSUMS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clear_staging() -> None:
    """Drop every leftover of an aborted run, so no truncated file survives."""
    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    if IMAGES_DIR.is_dir():
        for leftover in IMAGES_DIR.glob(f"*{IMAGE_PART_SUFFIX}"):
            leftover.unlink(missing_ok=True)


def _manual_hint(name: str, directory: Path, source: str, reason: object) -> str:
    return (
        f"Could not download {name}: {reason}\n"
        f"Download it by hand from {source}\n"
        f"and put it into {directory}"
    )


def _download_weight(name: str) -> Path:
    """Resolve a weight file through Ultralytics' own asset resolver.

    The release tag of the assets repository moves, so a hardcoded URL would
    break silently; the resolver knows the current one.
    """
    from ultralytics.utils.downloads import attempt_download_asset

    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    staged = STAGING_DIR / name
    staged.unlink(missing_ok=True)
    try:
        attempt_download_asset(staged)
    except Exception as err:  # network, HTTP status, unknown asset name
        raise FetchError(_manual_hint(name, MODELS_DIR, ASSET_RELEASES_PAGE, err)) from err
    if not staged.is_file():
        raise FetchError(
            _manual_hint(
                name,
                MODELS_DIR,
                ASSET_RELEASES_PAGE,
                "the Ultralytics resolver does not know this asset",
            )
        )
    return staged


def _download_test_image() -> Path:
    from ultralytics.utils.downloads import safe_download

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    staged = IMAGES_DIR / (TEST_IMAGE_NAME + IMAGE_PART_SUFFIX)
    staged.unlink(missing_ok=True)
    try:
        safe_download(
            url=TEST_IMAGE_URL,
            file=staged,
            unzip=False,
            min_bytes=MIN_IMAGE_BYTES,
            progress=True,
        )
    except Exception as err:
        raise FetchError(
            _manual_hint(TEST_IMAGE_NAME, IMAGES_DIR, TEST_IMAGE_URL, err)
        ) from err
    if not staged.is_file():
        raise FetchError(
            _manual_hint(TEST_IMAGE_NAME, IMAGES_DIR, TEST_IMAGE_URL, "no file was written")
        )
    return staged


def _verify_download(staged: Path, name: str) -> None:
    """Refuse a staged file that is not whole, so it never reaches its target."""
    min_bytes = MIN_BYTES[name]
    size = staged.stat().st_size
    if size < min_bytes:
        raise FetchError(
            f"Download of {name} stopped short: {size} bytes, "
            f"expected at least {min_bytes}. Nothing was moved into place; "
            f"run this script again."
        )
    if name in ZIP_CONTAINER_TARGETS and not zipfile.is_zipfile(staged):
        raise FetchError(
            f"Download of {name} is damaged: {size} bytes on disk, but the file "
            f"is not a complete checkpoint. Nothing was moved into place; "
            f"run this script again."
        )


def _print_summary(rows: list[tuple[str, int, str, str]]) -> None:
    print()
    print(f"{'FILE':<28}{'SIZE':>10}  {'STATUS':<12}SHA256")
    for name, size, digest, status in rows:
        print(f"{name:<28}{_human_size(size):>10}  {status:<12}{digest}")
    downloaded = sum(1 for row in rows if row[3] == "downloaded")
    print(
        f"\n{len(rows)} file(s) ready in {MODELS_DIR} and {IMAGES_DIR} "
        f"({downloaded} downloaded, {len(rows) - downloaded} already present)."
    )
    print(f"Checksums: {CHECKSUMS_FILE}")


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    _clear_staging()

    targets: list[tuple[str, Path, object]] = [
        (name, MODELS_DIR / name, (lambda n=name: _download_weight(n)))
        for name in WEIGHT_NAMES
    ]
    targets.append((TEST_IMAGE_NAME, IMAGES_DIR / TEST_IMAGE_NAME, _download_test_image))

    sums = _read_checksums()
    rows: list[tuple[str, int, str, str]] = []

    try:
        for name, target, download in targets:
            key = _rel(target)
            digest = _sha256(target) if target.is_file() else None
            if digest is not None and sums.get(key) == digest:
                status = "skip"
            else:
                staged = download()
                _verify_download(staged, name)
                target.unlink(missing_ok=True)
                staged.replace(target)
                digest = _sha256(target)
                status = "downloaded"
            sums[key] = digest
            # Written after every file, so an interrupted run does not throw
            # away what it already fetched.
            _write_checksums(sums)
            rows.append((key, target.stat().st_size, digest, status))
    except FetchError as err:
        print(str(err), file=sys.stderr)
        return 1
    finally:
        _clear_staging()

    _print_summary(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
