"""Archive a one-dir bundle to a ``.zip`` (Phase 0 decision D17, stdlib zipfile).

The archive stores files relative to the bundle root so that extracting it yields
the bundle contents directly into a target directory.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from drivedeploy.errors import ArtifactNotFoundError


def zip_bundle(src_dir: Path, dest_zip: Path) -> Path:
    """Zip the contents of ``src_dir`` into ``dest_zip`` and return ``dest_zip``."""
    src_dir = Path(src_dir)
    dest_zip = Path(dest_zip)
    if not src_dir.is_dir():
        raise ArtifactNotFoundError(f"Bundle directory not found: {src_dir}")

    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in sorted(src_dir.rglob("*")):
            if entry.is_file():
                archive.write(entry, entry.relative_to(src_dir).as_posix())
    return dest_zip


def extract_bundle(src_zip: Path, dest_dir: Path) -> Path:
    """Extract a bundle ``.zip`` into ``dest_dir`` and return ``dest_dir``."""
    src_zip = Path(src_zip)
    dest_dir = Path(dest_dir)
    if not src_zip.is_file():
        raise ArtifactNotFoundError(f"Archive not found: {src_zip}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src_zip, "r") as archive:
        archive.extractall(dest_dir)
    return dest_dir
