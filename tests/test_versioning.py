"""Tests for drivedeploy.core.versioning."""

from __future__ import annotations

import pytest

from drivedeploy.core import versioning
from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.errors import ConfigError


def _cfg(version_source: str) -> DriveDeployConfig:
    return DriveDeployConfig(
        name="mytool", location="X:/t", version_source=version_source
    )


def _write_pyproject(project_dir, body: str):
    project_dir.joinpath("pyproject.toml").write_text(body, encoding="utf-8")


def test_resolve_project_version(tmp_path):
    _write_pyproject(tmp_path, '[project]\nname = "x"\nversion = "2.3.4"\n')
    assert versioning.resolve_version(_cfg("project"), tmp_path) == "2.3.4"


def test_resolve_literal_version(tmp_path):
    assert versioning.resolve_version(_cfg("9.9.9"), tmp_path) == "9.9.9"


def test_resolve_project_missing_version_raises(tmp_path):
    _write_pyproject(tmp_path, '[project]\nname = "x"\n')
    with pytest.raises(ConfigError):
        versioning.resolve_version(_cfg("project"), tmp_path)


def test_resolve_dynamic_falls_back_to_vcs(tmp_path, monkeypatch):
    _write_pyproject(tmp_path, '[project]\nname = "x"\ndynamic = ["version"]\n')
    monkeypatch.setattr(versioning, "_git_describe", lambda _d: "1.2.3")
    assert versioning.resolve_version(_cfg("project"), tmp_path) == "1.2.3"


def test_resolve_vcs(tmp_path, monkeypatch):
    monkeypatch.setattr(versioning, "_git_describe", lambda _d: "4.5.6")
    assert versioning.resolve_version(_cfg("vcs"), tmp_path) == "4.5.6"


@pytest.mark.parametrize(
    ("candidate", "current", "expected"),
    [
        ("1.1.0", "1.0.0", True),
        ("1.0.0", "1.0.0", False),
        ("1.0.0", "1.1.0", False),
        ("2.0.0", "1.9.9", True),
        ("1.0.0rc1", "1.0.0", False),
        ("1.0.0", "1.0.0rc1", True),
    ],
)
def test_is_newer(candidate, current, expected):
    assert versioning.is_newer(candidate, current) is expected
