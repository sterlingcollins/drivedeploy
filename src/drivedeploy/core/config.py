"""Load and validate the consuming tool's ``[tool.drivedeploy]`` config.

The config lives in the *tool's* ``pyproject.toml`` (Phase 0 decision C5), not in
this library. Functions here are imported via the namespace (``from drivedeploy.core
import config``); the dataclass is imported directly.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from drivedeploy.core import platforms
from drivedeploy.errors import ConfigError

DEFAULT_CHANNEL = "release"
VALID_KINDS = ("onefile", "onedir")
DEFAULT_VERSION_SOURCE = "project"


@dataclass(frozen=True, slots=True)
class DriveDeployConfig:
    """Resolved-but-static deployment config for a single tool.

    ``artifact`` and ``version_source`` are build-time concerns and may be ``None``
    on the client side (where only the runtime fields matter).
    """

    name: str
    location: str
    channel: str | None = None
    platform: str | None = None
    artifact: str | None = None
    kind: str = "onefile"
    version_source: str = DEFAULT_VERSION_SOURCE

    def effective_channel(self) -> str:
        """Channel to publish/read from, defaulting to ``release`` (D5/D16)."""
        return self.channel or DEFAULT_CHANNEL

    def effective_platform(self) -> str:
        """Platform tag, derived from the build host when unset (D18)."""
        return self.platform or platforms.current_platform_tag()


def _read_pyproject(project_dir: Path) -> dict[str, Any]:
    pyproject = Path(project_dir) / "pyproject.toml"
    if not pyproject.is_file():
        raise ConfigError(f"No pyproject.toml found at {pyproject}.")
    try:
        with pyproject.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Failed to parse {pyproject}: {exc}") from exc


def parse_config(data: dict[str, Any]) -> DriveDeployConfig:
    """Build and validate a :class:`DriveDeployConfig` from parsed TOML data."""
    tool_table = data.get("tool", {}).get("drivedeploy")
    if not isinstance(tool_table, dict):
        raise ConfigError("Missing [tool.drivedeploy] table in pyproject.toml.")

    project_name = data.get("project", {}).get("name")
    name = tool_table.get("name") or project_name
    if not name:
        raise ConfigError(
            "Tool name not set: provide [tool.drivedeploy].name or [project].name."
        )

    location = tool_table.get("location")
    if not location or not str(location).strip():
        raise ConfigError("[tool.drivedeploy].location must be a non-empty path.")

    kind = tool_table.get("kind", "onefile")
    if kind not in VALID_KINDS:
        raise ConfigError(
            f"[tool.drivedeploy].kind must be one of {VALID_KINDS}, got {kind!r}."
        )

    return DriveDeployConfig(
        name=str(name),
        location=str(location),
        channel=tool_table.get("channel"),
        platform=tool_table.get("platform"),
        artifact=tool_table.get("artifact"),
        kind=kind,
        version_source=tool_table.get("version_source", DEFAULT_VERSION_SOURCE),
    )


def load_config(project_dir: Path = Path(".")) -> DriveDeployConfig:
    """Load and validate ``[tool.drivedeploy]`` from a project's ``pyproject.toml``."""
    return parse_config(_read_pyproject(Path(project_dir)))
