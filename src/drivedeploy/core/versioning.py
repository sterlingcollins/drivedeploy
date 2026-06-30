"""Version resolution and comparison.

Source of truth is ``[project].version`` by default; if that is dynamic, fall back
to VCS tags. The author may force ``vcs`` or pin a literal via ``version_source``
(Phase 0 decision D10).
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version

from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.errors import ConfigError


def _read_project_table(project_dir: Path) -> dict:
    pyproject = Path(project_dir) / "pyproject.toml"
    if not pyproject.is_file():
        return {}
    with pyproject.open("rb") as handle:
        return tomllib.load(handle).get("project", {})


def _git_describe(project_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--dirty", "--always"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigError(
            f"Could not resolve version from VCS in {project_dir}: {exc}"
        ) from exc
    tag = result.stdout.strip().lstrip("v")
    if not tag:
        raise ConfigError(f"git describe returned no version in {project_dir}.")
    return tag


def resolve_version(config: DriveDeployConfig, project_dir: Path = Path(".")) -> str:
    """Resolve the version string for a publish according to ``version_source``."""
    source = config.version_source or "project"
    project_dir = Path(project_dir)

    if source == "project":
        project = _read_project_table(project_dir)
        dynamic = project.get("dynamic", [])
        if "version" in dynamic:
            return _git_describe(project_dir)
        version = project.get("version")
        if not version:
            raise ConfigError(
                "version_source='project' but [project].version is unset and not "
                "declared dynamic."
            )
        return str(version)

    if source == "vcs":
        return _git_describe(project_dir)

    return str(source)


def is_newer(candidate: str, current: str) -> bool:
    """Return True when ``candidate`` is a strictly newer version than ``current``."""
    try:
        return Version(candidate) > Version(current)
    except InvalidVersion:
        return candidate != current and candidate > current
