"""Tests for drivedeploy.update.updater (check/apply selection; swap mocked)."""

from __future__ import annotations

from pathlib import Path

import pytest

from drivedeploy.core import hashing, layout, manifest
from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.core.manifest import ReleaseRecord
from drivedeploy.errors import ArtifactNotFoundError
from drivedeploy.update import swap_windows, updater
from drivedeploy.update.client_config import ClientConfig


def _publish_release(drive, version: str, payload: bytes) -> None:
    filename = f"release/mytool-{version}-win64.exe"
    target = drive / "mytool" / "release" / f"mytool-{version}-win64.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)

    man_path = layout.manifest_path(str(drive), "mytool")
    man = (
        manifest.read_manifest(man_path)
        if man_path.is_file()
        else manifest.new_manifest("mytool")
    )
    manifest.add_release(
        man,
        "release",
        ReleaseRecord(
            version=version,
            platform="win64",
            kind="onefile",
            filename=filename,
            sha256=hashing.sha256_bytes(payload),
            size=len(payload),
            published_at="2026-06-29T21:00:00Z",
        ),
    )
    manifest.write_manifest(man_path, man)


def _client(drive, version: str) -> ClientConfig:
    return ClientConfig(
        config=DriveDeployConfig(name="mytool", location=str(drive), kind="onefile"),
        version=version,
    )


@pytest.fixture
def fake_install(tmp_path, monkeypatch):
    install = tmp_path / "install"
    install.mkdir()
    exe = install / "mytool.exe"
    exe.write_bytes(b"old exe v1")
    monkeypatch.setattr(swap_windows, "current_executable", lambda: exe)
    return install, exe


def test_check_finds_newer(fake_drive):
    _publish_release(fake_drive, "1.0.0", b"v1")
    _publish_release(fake_drive, "1.1.0", b"v2")
    info = updater.check(client=_client(fake_drive, "1.0.0"))
    assert info is not None
    assert info.latest_version == "1.1.0"
    assert info.current_version == "1.0.0"
    assert info.channel == "release"


def test_check_current_returns_none(fake_drive):
    _publish_release(fake_drive, "1.0.0", b"v1")
    assert updater.check(client=_client(fake_drive, "1.0.0")) is None


def test_check_running_ahead_returns_none(fake_drive):
    _publish_release(fake_drive, "1.0.0", b"v1")
    assert updater.check(client=_client(fake_drive, "2.0.0")) is None


def test_apply_staged_writes_marker(fake_drive, fake_install):
    install, exe = fake_install
    _publish_release(fake_drive, "1.0.0", b"v1")
    _publish_release(fake_drive, "1.1.0", b"new payload v2")

    mode = updater.apply(strategy="staged", client=_client(fake_drive, "1.0.0"))
    assert mode == "staged"

    pending = swap_windows.read_pending(install)
    assert pending is not None
    assert pending.version == "1.1.0"
    assert Path(pending.staged_path).read_bytes() == b"new payload v2"


def test_apply_rollback_selects_explicit_version(fake_drive, fake_install):
    install, _ = fake_install
    _publish_release(fake_drive, "1.0.0", b"older payload")
    _publish_release(fake_drive, "1.1.0", b"newer payload")

    mode = updater.apply(
        version="1.0.0", strategy="staged", client=_client(fake_drive, "1.1.0")
    )
    assert mode == "staged"
    assert swap_windows.read_pending(install).version == "1.0.0"


def test_apply_live_invokes_swap(fake_drive, fake_install, monkeypatch):
    calls = {}

    def fake_swap(target, new, *, relaunch_after):
        calls["target"] = target
        calls["relaunch"] = relaunch_after

    monkeypatch.setattr(swap_windows, "swap_onefile_live", fake_swap)
    _publish_release(fake_drive, "1.1.0", b"new")

    mode = updater.apply(
        strategy="live", relaunch=False, client=_client(fake_drive, "1.0.0")
    )
    assert mode == "live"
    assert calls["relaunch"] is False


def test_apply_auto_falls_back_to_staged_on_oserror(
    fake_drive, fake_install, monkeypatch
):
    install, _ = fake_install

    def boom(*_a, **_k):
        raise OSError("AV blocked the swap")

    monkeypatch.setattr(swap_windows, "swap_onefile_live", boom)
    _publish_release(fake_drive, "1.1.0", b"new")

    mode = updater.apply(strategy="auto", client=_client(fake_drive, "1.0.0"))
    assert mode == "staged"
    assert swap_windows.read_pending(install) is not None


def test_apply_unknown_version_raises(fake_drive, fake_install):
    _publish_release(fake_drive, "1.0.0", b"v1")
    with pytest.raises(ArtifactNotFoundError):
        updater.apply(version="9.9.9", client=_client(fake_drive, "1.0.0"))
