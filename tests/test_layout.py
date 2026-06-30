"""Tests for drivedeploy.core.layout."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from drivedeploy.core import layout


def test_artifact_extension():
    assert layout.artifact_extension("onefile") == "exe"
    assert layout.artifact_extension("onedir") == "zip"


def test_artifact_extension_unknown():
    with pytest.raises(ValueError):
        layout.artifact_extension("nope")


def test_artifact_filename_onefile():
    assert (
        layout.artifact_filename("mytool", "1.4.0", "win64", "onefile")
        == "mytool-1.4.0-win64.exe"
    )


def test_artifact_filename_onedir():
    assert (
        layout.artifact_filename("mytool", "1.4.0", "win64", "onedir")
        == "mytool-1.4.0-win64.zip"
    )


def test_manifest_path():
    p = layout.manifest_path("X:/tools", "mytool")
    assert p == Path("X:/tools") / "mytool" / "manifest.json"


def test_channel_dir():
    p = layout.channel_dir("X:/tools", "mytool", "release")
    assert p == Path("X:/tools") / "mytool" / "release"


def test_artifact_relpath_uses_posix():
    rel = layout.artifact_relpath("release", "mytool-1.0.0-win64.exe")
    assert rel == "release/mytool-1.0.0-win64.exe"
    assert "\\" not in rel


def test_artifact_path_for_release():
    p = layout.artifact_path_for_release(
        "X:/tools", "mytool", "release/mytool-1.0.0-win64.exe"
    )
    expected = (
        Path("X:/tools") / "mytool" / PurePosixPath("release/mytool-1.0.0-win64.exe")
    )
    assert p == expected
