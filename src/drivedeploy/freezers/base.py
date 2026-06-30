"""Freezer interface.

A freezer knows how to locate the frozen artifact a maintainer produced (one-file
exe or one-dir bundle). The interface keeps Phase 0 decision D14 open so other
backends (Nuitka, cx_Freeze) can slot in later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from drivedeploy.core.config import DriveDeployConfig


@dataclass(frozen=True, slots=True)
class FrozenArtifact:
    """The located build output for a tool.

    ``path`` points to a file for ``onefile`` builds and a directory for ``onedir``.
    """

    path: Path
    kind: str


@runtime_checkable
class Freezer(Protocol):
    """Protocol implemented by each freezer backend."""

    name: str

    def locate(self, config: DriveDeployConfig, project_dir: Path) -> FrozenArtifact:
        """Locate the frozen artifact for ``config`` under ``project_dir``."""
        ...
