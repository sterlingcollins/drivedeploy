"""Tests for drivedeploy.core.config."""

from __future__ import annotations

import pytest

from drivedeploy.core import config
from drivedeploy.errors import ConfigError


def _data(**tool):
    base = {"project": {"name": "fromproject"}, "tool": {"drivedeploy": tool}}
    return base


def test_parse_minimal_uses_project_name():
    cfg = config.parse_config(_data(location="\\\\share\\tools"))
    assert cfg.name == "fromproject"
    assert cfg.location == "\\\\share\\tools"
    assert cfg.kind == "onefile"
    assert cfg.version_source == "project"


def test_tool_name_overrides_project_name():
    cfg = config.parse_config(_data(name="mytool", location="X:/tools"))
    assert cfg.name == "mytool"


def test_effective_channel_defaults_to_release():
    cfg = config.parse_config(_data(location="X:/tools"))
    assert cfg.effective_channel() == "release"


def test_effective_channel_explicit():
    cfg = config.parse_config(_data(location="X:/tools", channel="beta"))
    assert cfg.effective_channel() == "beta"


def test_effective_platform_defaults_to_win64():
    cfg = config.parse_config(_data(location="X:/tools"))
    assert cfg.effective_platform() == "win64"


def test_missing_table_raises():
    with pytest.raises(ConfigError):
        config.parse_config({"project": {"name": "x"}})


def test_missing_location_raises():
    with pytest.raises(ConfigError):
        config.parse_config(_data(name="mytool"))


def test_blank_location_raises():
    with pytest.raises(ConfigError):
        config.parse_config(_data(location="   "))


def test_invalid_kind_raises():
    with pytest.raises(ConfigError):
        config.parse_config(_data(location="X:/t", kind="weird"))


def test_missing_name_everywhere_raises():
    with pytest.raises(ConfigError):
        config.parse_config({"tool": {"drivedeploy": {"location": "X:/t"}}})


def test_load_config_from_project(onefile_project):
    cfg = config.load_config(onefile_project)
    assert cfg.name == "mytool"
    assert cfg.kind == "onefile"


def test_load_config_missing_pyproject_raises(tmp_path):
    with pytest.raises(ConfigError):
        config.load_config(tmp_path)
