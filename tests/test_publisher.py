"""Tests for drivedeploy.publish.publisher (full publish over the fake drive)."""

from __future__ import annotations

import zipfile

from drivedeploy.core import hashing, layout, manifest
from drivedeploy.publish import publisher


def test_publish_onefile(onefile_project, fake_drive):
    record = publisher.publish(onefile_project)

    assert record.version == "1.0.0"
    assert record.platform == "win64"
    assert record.kind == "onefile"
    assert record.filename == "release/mytool-1.0.0-win64.exe"

    artifact = layout.artifact_path_for_release(
        str(fake_drive), "mytool", record.filename
    )
    assert artifact.is_file()
    assert hashing.sha256_file(artifact) == record.sha256

    man = manifest.read_manifest(layout.manifest_path(str(fake_drive), "mytool"))
    assert man.channel("release").latest == "1.0.0"


def test_publish_onedir_archives_zip(onedir_project, fake_drive):
    record = publisher.publish(onedir_project)

    assert record.kind == "onedir"
    assert record.filename == "release/mytool-1.0.0-win64.zip"

    artifact = layout.artifact_path_for_release(
        str(fake_drive), "mytool", record.filename
    )
    assert artifact.is_file()
    with zipfile.ZipFile(artifact) as zf:
        names = set(zf.namelist())
    assert "mytool.exe" in names
    assert "_internal/data.bin" in names


def test_publish_dry_run_writes_nothing(onefile_project, fake_drive):
    record = publisher.publish(onefile_project, dry_run=True)
    assert record.version == "1.0.0"
    assert not (fake_drive / "mytool").exists()


def test_publish_channel_override(onefile_project, fake_drive):
    record = publisher.publish(onefile_project, channel="beta")
    assert record.filename == "release".replace("release", "beta") + (
        "/mytool-1.0.0-win64.exe"
    )
    man = manifest.read_manifest(layout.manifest_path(str(fake_drive), "mytool"))
    assert man.channel("beta").latest == "1.0.0"


def test_publish_version_override(onefile_project, fake_drive):
    record = publisher.publish(onefile_project, version="9.9.9")
    assert record.version == "9.9.9"
    assert record.filename == "release/mytool-9.9.9-win64.exe"


def test_publish_twice_keeps_both_releases(onefile_project, fake_drive):
    publisher.publish(onefile_project, version="1.0.0")
    publisher.publish(onefile_project, version="1.1.0")
    man = manifest.read_manifest(layout.manifest_path(str(fake_drive), "mytool"))
    versions = {r.version for r in man.channel("release").releases}
    assert versions == {"1.0.0", "1.1.0"}
    assert man.channel("release").latest == "1.1.0"
