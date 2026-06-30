"""Copy a release artifact from the drive to a local temp dir and verify checksum."""

from __future__ import annotations

import shutil
from pathlib import Path

from drivedeploy.core import hashing, layout
from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.core.manifest import ReleaseRecord
from drivedeploy.errors import ArtifactNotFoundError, IntegrityError


def fetch(config: DriveDeployConfig, release: ReleaseRecord, dest_dir: Path) -> Path:
    """Copy ``release`` from the drive into ``dest_dir`` and verify its SHA256.

    Returns the path to the downloaded file. Raises :class:`IntegrityError` on a
    checksum mismatch (the partial download is removed first).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    source = layout.artifact_path_for_release(
        config.location, config.name, release.filename
    )
    if not source.is_file():
        raise ArtifactNotFoundError(f"Release artifact not found on drive: {source}")

    local = dest_dir / Path(release.filename).name
    shutil.copy2(source, local)

    actual = hashing.sha256_file(local)
    if actual != release.sha256:
        local.unlink(missing_ok=True)
        raise IntegrityError(
            f"Checksum mismatch for {release.filename}: "
            f"expected {release.sha256}, got {actual}."
        )
    return local
