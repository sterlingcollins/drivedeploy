"""Tests for the generated embed module (drivedeploy.publish.embed) + client load."""

from __future__ import annotations

import importlib
import importlib.util
import sys

import pytest

from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.publish import embed
from drivedeploy.update import client_config


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cfg(**over) -> DriveDeployConfig:
    base = {
        "name": "mytool",
        "location": r"\\share\tools\drivedeploy",
        "channel": "beta",
        "platform": "win64",
        "artifact": "dist/mytool.exe",
        "kind": "onefile",
        "version_source": "project",
    }
    base.update(over)
    return DriveDeployConfig(**base)


def test_generated_file_is_importable(tmp_path):
    path = embed.generate_embed_module(_cfg(), "1.2.3", tmp_path)
    assert path.name == "_drivedeploy_embed.py"
    module = _load_module(path, "embed_importable")
    assert module.NAME == "mytool"
    assert module.VERSION == "1.2.3"


def test_round_trips_to_same_config(tmp_path):
    cfg = _cfg()
    path = embed.generate_embed_module(cfg, "1.2.3", tmp_path)
    module = _load_module(path, "embed_round_trip")
    client = client_config.from_module(module)
    assert client.config == cfg
    assert client.version == "1.2.3"


def test_round_trips_with_optional_none(tmp_path):
    cfg = _cfg(channel=None, platform=None, artifact=None)
    path = embed.generate_embed_module(cfg, "2.0.0", tmp_path)
    module = _load_module(path, "embed_optional_none")
    client = client_config.from_module(module)
    assert client.config == cfg
    assert client.config.effective_channel() == "release"


def test_backslash_location_survives(tmp_path):
    cfg = _cfg(location=r"\\server\share\with space\drivedeploy")
    path = embed.generate_embed_module(cfg, "1.0.0", tmp_path)
    module = _load_module(path, "embed_backslash")
    assert module.LOCATION == r"\\server\share\with space\drivedeploy"


def test_client_config_load_by_name(tmp_path, monkeypatch):
    embed.generate_embed_module(_cfg(), "3.1.4", tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop(embed.EMBED_MODULE_NAME, None)
    try:
        client = client_config.load()
        assert client.version == "3.1.4"
        assert client.config.name == "mytool"
    finally:
        sys.modules.pop(embed.EMBED_MODULE_NAME, None)


def test_client_config_load_missing_raises(monkeypatch):
    from drivedeploy.errors import ConfigError

    sys.modules.pop("nonexistent_embed_xyz", None)
    with pytest.raises(ConfigError):
        client_config.load("nonexistent_embed_xyz")
