"""Tests for drivedeploy.freezers.pyinstaller."""

from __future__ import annotations

import pytest

from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.errors import ArtifactNotFoundError, ConfigError
from drivedeploy.freezers import pyinstaller
from drivedeploy.freezers.base import Freezer, FrozenArtifact


def _cfg(tmp_path, kind, artifact) -> DriveDeployConfig:
    return DriveDeployConfig(
        name="mytool", location="X:/t", kind=kind, artifact=artifact
    )


def test_locate_onefile(onefile_project):
    cfg = DriveDeployConfig(
        name="mytool", location="X:/t", kind="onefile", artifact="dist/mytool.exe"
    )
    art = pyinstaller.locate(cfg, onefile_project)
    assert isinstance(art, FrozenArtifact)
    assert art.kind == "onefile"
    assert art.path.is_file()


def test_locate_onedir(onedir_project):
    cfg = DriveDeployConfig(
        name="mytool", location="X:/t", kind="onedir", artifact="dist/mytool"
    )
    art = pyinstaller.locate(cfg, onedir_project)
    assert art.kind == "onedir"
    assert art.path.is_dir()


def test_locate_missing_raises(tmp_path):
    cfg = _cfg(tmp_path, "onefile", "dist/missing.exe")
    with pytest.raises(ArtifactNotFoundError):
        pyinstaller.locate(cfg, tmp_path)


def test_locate_kind_mismatch_raises(onedir_project):
    cfg = DriveDeployConfig(
        name="mytool", location="X:/t", kind="onefile", artifact="dist/mytool"
    )
    with pytest.raises(ConfigError):
        pyinstaller.locate(cfg, onedir_project)


def test_pyinstaller_freezer_satisfies_protocol():
    assert isinstance(pyinstaller.PyInstallerFreezer(), Freezer)
