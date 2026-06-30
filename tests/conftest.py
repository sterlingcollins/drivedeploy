"""Shared fixtures: a temp-dir-backed fake drive and sample project trees."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fake_drive(tmp_path: Path) -> Path:
    """A temp directory standing in for the shared network drive."""
    drive = tmp_path / "drive"
    drive.mkdir()
    return drive


def _write_pyproject(
    project_dir: Path, location: Path, *, kind: str, version: str = "1.0.0"
) -> None:
    artifact = "dist/mytool.exe" if kind == "onefile" else "dist/mytool"
    project_dir.joinpath("pyproject.toml").write_text(
        f"""
[project]
name = "mytool"
version = "{version}"

[tool.drivedeploy]
location = {str(location)!r}
kind = "{kind}"
artifact = "{artifact}"
""",
        encoding="utf-8",
    )


@pytest.fixture
def onefile_project(tmp_path: Path, fake_drive: Path) -> Path:
    """A project configured for a one-file build with a fake frozen exe."""
    project = tmp_path / "proj_onefile"
    (project / "dist").mkdir(parents=True)
    (project / "dist" / "mytool.exe").write_bytes(b"MZ fake exe payload v1")
    _write_pyproject(project, fake_drive, kind="onefile")
    return project


@pytest.fixture
def onedir_project(tmp_path: Path, fake_drive: Path) -> Path:
    """A project configured for a one-dir build with a fake bundle directory."""
    project = tmp_path / "proj_onedir"
    bundle = project / "dist" / "mytool"
    bundle.mkdir(parents=True)
    (bundle / "mytool.exe").write_bytes(b"MZ fake exe payload v1")
    (bundle / "_internal").mkdir()
    (bundle / "_internal" / "data.bin").write_bytes(b"some data")
    _write_pyproject(project, fake_drive, kind="onedir")
    return project
