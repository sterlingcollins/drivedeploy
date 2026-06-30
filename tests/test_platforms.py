"""Tests for drivedeploy.core.platforms."""

from __future__ import annotations

import pytest

from drivedeploy.core import platforms
from drivedeploy.errors import UnsupportedPlatformError


def test_current_platform_tag_is_win64():
    assert platforms.current_platform_tag() == "win64"


def test_ensure_windows_raises_off_windows(monkeypatch):
    monkeypatch.setattr(platforms.sys, "platform", "linux")
    with pytest.raises(UnsupportedPlatformError):
        platforms.ensure_windows()


def test_ensure_windows_is_notimplementederror(monkeypatch):
    monkeypatch.setattr(platforms.sys, "platform", "darwin")
    with pytest.raises(NotImplementedError):
        platforms.ensure_windows()


def test_ensure_windows_ok_on_windows(monkeypatch):
    monkeypatch.setattr(platforms.sys, "platform", "win32")
    platforms.ensure_windows()
