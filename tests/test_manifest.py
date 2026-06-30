"""Tests for drivedeploy.core.manifest."""

from __future__ import annotations

import json

import pytest

from drivedeploy.core import manifest
from drivedeploy.core.manifest import Manifest, ReleaseRecord
from drivedeploy.errors import ManifestError


def _release(version: str, **over) -> ReleaseRecord:
    base = {
        "version": version,
        "platform": "win64",
        "kind": "onefile",
        "filename": f"release/mytool-{version}-win64.exe",
        "sha256": "0" * 64,
        "size": 123,
        "published_at": "2026-06-29T21:00:00Z",
        "notes": None,
    }
    base.update(over)
    return ReleaseRecord(**base)


def test_round_trip(tmp_path):
    man = manifest.new_manifest("mytool")
    manifest.add_release(man, "release", _release("1.0.0"))
    path = tmp_path / "mytool" / "manifest.json"
    manifest.write_manifest(path, man)

    loaded = manifest.read_manifest(path)
    assert loaded.tool == "mytool"
    assert loaded.schema_version == manifest.SCHEMA_VERSION
    assert loaded.channel("release").latest == "1.0.0"
    assert loaded.channel("release").find("1.0.0").size == 123


def test_atomic_write_replaces_existing(tmp_path):
    path = tmp_path / "manifest.json"
    man = manifest.new_manifest("mytool")
    manifest.add_release(man, "release", _release("1.0.0"))
    manifest.write_manifest(path, man)

    manifest.add_release(man, "release", _release("1.1.0"))
    manifest.write_manifest(path, man)

    loaded = manifest.read_manifest(path)
    assert loaded.channel("release").latest == "1.1.0"
    assert len(loaded.channel("release").releases) == 2
    # No temp files left behind.
    assert list(tmp_path.glob("*.tmp")) == []


def test_add_release_refreshes_latest_regardless_of_order():
    man = manifest.new_manifest("mytool")
    manifest.add_release(man, "release", _release("1.2.0"))
    manifest.add_release(man, "release", _release("1.10.0"))
    manifest.add_release(man, "release", _release("1.3.0"))
    assert man.channel("release").latest == "1.10.0"


def test_add_release_upserts_same_version():
    man = manifest.new_manifest("mytool")
    manifest.add_release(man, "release", _release("1.0.0", size=1))
    manifest.add_release(man, "release", _release("1.0.0", size=999))
    rel = man.channel("release")
    assert len(rel.releases) == 1
    assert rel.find("1.0.0").size == 999


def test_read_missing_raises(tmp_path):
    with pytest.raises(ManifestError):
        manifest.read_manifest(tmp_path / "nope.json")


def test_read_invalid_json_raises(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError):
        manifest.read_manifest(path)


def test_from_dict_missing_tool_raises():
    with pytest.raises(ManifestError):
        Manifest.from_dict({"schema_version": 1, "channels": {}})


def test_malformed_release_raises():
    with pytest.raises(ManifestError):
        ReleaseRecord.from_dict({"version": "1.0.0"})


def test_serialized_shape(tmp_path):
    man = manifest.new_manifest("mytool")
    manifest.add_release(man, "release", _release("1.0.0"))
    path = tmp_path / "manifest.json"
    manifest.write_manifest(path, man)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["tool"] == "mytool"
    assert data["channels"]["release"]["latest"] == "1.0.0"
    assert data["channels"]["release"]["releases"][0]["sha256"] == "0" * 64
