"""Tests for drivedeploy.update.swap_windows (planning, staging, finalize)."""

from __future__ import annotations

import pytest

from drivedeploy.publish import archive
from drivedeploy.update import swap_windows
from drivedeploy.update.swap_windows import PendingUpdate


@pytest.mark.parametrize(
    ("strategy", "kind", "expected"),
    [
        ("auto", "onefile", "live"),
        ("auto", "onedir", "live"),
        ("live", "onefile", "live"),
        ("staged", "onefile", "staged"),
        ("staged", "onedir", "staged"),
    ],
)
def test_plan_swap(strategy, kind, expected):
    assert swap_windows.plan_swap(strategy, kind) == expected


def test_plan_swap_invalid_strategy():
    with pytest.raises(ValueError):
        swap_windows.plan_swap("nope", "onefile")


def test_plan_swap_invalid_kind():
    with pytest.raises(ValueError):
        swap_windows.plan_swap("auto", "weird")


def test_marker_round_trip(tmp_path):
    pending = PendingUpdate(
        version="1.1.0",
        kind="onefile",
        staged_path=str(tmp_path / "staged" / "mytool.exe"),
        target_path=str(tmp_path / "mytool.exe"),
        created_at="2026-06-29T21:00:00Z",
    )
    swap_windows.write_pending(tmp_path, pending)
    assert swap_windows.read_pending(tmp_path) == pending
    swap_windows.clear_pending(tmp_path)
    assert swap_windows.read_pending(tmp_path) is None


def test_read_pending_absent(tmp_path):
    assert swap_windows.read_pending(tmp_path) is None


def test_read_pending_corrupt_returns_none(tmp_path):
    swap_windows.marker_path(tmp_path).write_text("{bad json", encoding="utf-8")
    assert swap_windows.read_pending(tmp_path) is None


def test_stage_update_onefile(tmp_path):
    install = tmp_path / "install"
    install.mkdir()
    target = install / "mytool.exe"
    target.write_bytes(b"old")
    downloaded = tmp_path / "dl" / "mytool-1.1.0-win64.exe"
    downloaded.parent.mkdir()
    downloaded.write_bytes(b"new payload")

    pending = swap_windows.stage_update(
        install, downloaded, kind="onefile", version="1.1.0", target_path=target
    )
    assert pending.version == "1.1.0"
    staged = install / swap_windows.STAGE_DIR_NAME / "mytool.exe"
    assert staged.read_bytes() == b"new payload"
    assert swap_windows.read_pending(install) == pending


def test_finalize_onefile(tmp_path, monkeypatch):
    install = tmp_path / "install"
    install.mkdir()
    target = install / "mytool.exe"
    target.write_bytes(b"old exe")
    downloaded = tmp_path / "mytool-1.1.0-win64.exe"
    downloaded.write_bytes(b"new exe")
    swap_windows.stage_update(
        install, downloaded, kind="onefile", version="1.1.0", target_path=target
    )

    monkeypatch.setattr(swap_windows, "is_windows", lambda: False)
    applied = swap_windows.finalize_pending(install, relaunch_after=False)
    assert applied is True
    assert target.read_bytes() == b"new exe"
    assert swap_windows.read_pending(install) is None
    assert not (install / swap_windows.STAGE_DIR_NAME).exists()


def test_finalize_nothing_pending(tmp_path):
    assert swap_windows.finalize_pending(tmp_path, relaunch_after=False) is False


def test_finalize_onedir(tmp_path, monkeypatch):
    # Bundle dir is the install target; marker/stage live in its parent.
    parent = tmp_path / "apps"
    bundle = parent / "mytool"
    bundle.mkdir(parents=True)
    (bundle / "mytool.exe").write_bytes(b"old exe")
    (bundle / "old_only.txt").write_text("remove me", encoding="utf-8")

    # Build a new bundle and zip it as the "downloaded" artifact.
    new_bundle = tmp_path / "newbundle"
    new_bundle.mkdir()
    (new_bundle / "mytool.exe").write_bytes(b"new exe")
    (new_bundle / "fresh.txt").write_text("hello", encoding="utf-8")
    zipped = archive.zip_bundle(new_bundle, tmp_path / "mytool-1.1.0-win64.zip")

    swap_windows.stage_update(
        parent, zipped, kind="onedir", version="1.1.0", target_path=bundle
    )

    monkeypatch.setattr(swap_windows, "is_windows", lambda: False)
    applied = swap_windows.finalize_pending(parent, relaunch_after=False)
    assert applied is True
    assert (bundle / "mytool.exe").read_bytes() == b"new exe"
    assert (bundle / "fresh.txt").read_text(encoding="utf-8") == "hello"
    assert not (bundle / "old_only.txt").exists()


def test_finalize_auto_search_onefile(tmp_path, monkeypatch):
    install = tmp_path / "install"
    install.mkdir()
    target = install / "mytool.exe"
    target.write_bytes(b"old")
    downloaded = tmp_path / "new.exe"
    downloaded.write_bytes(b"new")
    swap_windows.stage_update(
        install, downloaded, kind="onefile", version="1.1.0", target_path=target
    )
    monkeypatch.setattr(swap_windows, "current_executable", lambda: target)
    monkeypatch.setattr(swap_windows, "is_windows", lambda: False)
    assert swap_windows.finalize_pending(relaunch_after=False) is True
    assert target.read_bytes() == b"new"


def test_cleanup_old_onefile(tmp_path):
    target = tmp_path / "mytool.exe"
    old = tmp_path / ("mytool.exe" + swap_windows.OLD_SUFFIX)
    old.write_bytes(b"stale")
    swap_windows.cleanup_old_onefile(target)
    assert not old.exists()
