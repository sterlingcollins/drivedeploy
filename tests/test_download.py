"""Tests for drivedeploy.update.download (copy-from-drive + checksum verify)."""

from __future__ import annotations

import pytest

from drivedeploy.core import hashing
from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.core.manifest import ReleaseRecord
from drivedeploy.errors import ArtifactNotFoundError, IntegrityError
from drivedeploy.update import download


def _config(location) -> DriveDeployConfig:
    return DriveDeployConfig(name="mytool", location=str(location))


def _place_artifact(drive, payload: bytes) -> ReleaseRecord:
    rel = "release/mytool-1.0.0-win64.exe"
    target = drive / "mytool" / "release" / "mytool-1.0.0-win64.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return ReleaseRecord(
        version="1.0.0",
        platform="win64",
        kind="onefile",
        filename=rel,
        sha256=hashing.sha256_bytes(payload),
        size=len(payload),
        published_at="2026-06-29T21:00:00Z",
    )


def test_fetch_ok(fake_drive, tmp_path):
    payload = b"new exe payload v2"
    release = _place_artifact(fake_drive, payload)
    local = download.fetch(_config(fake_drive), release, tmp_path / "dl")
    assert local.is_file()
    assert local.read_bytes() == payload


def test_fetch_checksum_mismatch_raises_and_cleans(fake_drive, tmp_path):
    release = _place_artifact(fake_drive, b"payload")
    bad = ReleaseRecord(
        version=release.version,
        platform=release.platform,
        kind=release.kind,
        filename=release.filename,
        sha256="f" * 64,
        size=release.size,
        published_at=release.published_at,
    )
    dest = tmp_path / "dl"
    with pytest.raises(IntegrityError):
        download.fetch(_config(fake_drive), bad, dest)
    assert list(dest.glob("*")) == []


def test_fetch_missing_artifact_raises(fake_drive, tmp_path):
    release = ReleaseRecord(
        version="1.0.0",
        platform="win64",
        kind="onefile",
        filename="release/absent.exe",
        sha256="0" * 64,
        size=1,
        published_at="2026-06-29T21:00:00Z",
    )
    with pytest.raises(ArtifactNotFoundError):
        download.fetch(_config(fake_drive), release, tmp_path / "dl")
