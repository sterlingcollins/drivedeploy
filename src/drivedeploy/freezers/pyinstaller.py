"""PyInstaller freezer backend.

PyInstaller writes its output under ``dist/``. The maintainer points
``[tool.drivedeploy].artifact`` at that output (the ``.exe`` for one-file, or the
bundle directory for one-dir). This backend resolves and validates that path.
"""

from __future__ import annotations

from pathlib import Path

from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.errors import ArtifactNotFoundError, ConfigError
from drivedeploy.freezers.base import FrozenArtifact

name = "pyinstaller"


def _default_artifact(config: DriveDeployConfig) -> str:
    if config.kind == "onedir":
        return str(Path("dist") / config.name)
    return str(Path("dist") / f"{config.name}.exe")


def locate(config: DriveDeployConfig, project_dir: Path = Path(".")) -> FrozenArtifact:
    """Locate and validate the PyInstaller output for ``config``."""
    artifact = config.artifact or _default_artifact(config)
    path = Path(project_dir) / artifact

    if not path.exists():
        raise ArtifactNotFoundError(
            f"Frozen artifact not found at {path}. Build it before publishing."
        )

    if config.kind == "onefile" and not path.is_file():
        raise ConfigError(f"kind='onefile' but artifact {path} is not a file.")
    if config.kind == "onedir" and not path.is_dir():
        raise ConfigError(f"kind='onedir' but artifact {path} is not a directory.")

    return FrozenArtifact(path=path, kind=config.kind)


class PyInstallerFreezer:
    """Object form of the PyInstaller backend (satisfies the :class:`Freezer`)."""

    name = "pyinstaller"

    def locate(
        self, config: DriveDeployConfig, project_dir: Path = Path(".")
    ) -> FrozenArtifact:
        return locate(config, project_dir)
