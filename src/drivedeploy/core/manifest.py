"""JSON manifest model with atomic read/write (Phase 0 decision D3).

Schema mirrors ``Phase0_Overview.md`` §6 (``schema_version: 1``). Manifest writes
use write-temp-then-:func:`os.replace` for atomicity.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from drivedeploy.errors import ManifestError

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ReleaseRecord:
    """A single published artifact within a channel."""

    version: str
    platform: str
    kind: str
    filename: str
    sha256: str
    size: int
    published_at: str
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleaseRecord:
        try:
            return cls(
                version=str(data["version"]),
                platform=str(data["platform"]),
                kind=str(data["kind"]),
                filename=str(data["filename"]),
                sha256=str(data["sha256"]),
                size=int(data["size"]),
                published_at=str(data["published_at"]),
                notes=data.get("notes"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError(f"Malformed release record: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Channel:
    """A release track holding an ordered list of releases and a ``latest`` pointer."""

    latest: str | None = None
    releases: list[ReleaseRecord] = field(default_factory=list)

    def find(self, version: str) -> ReleaseRecord | None:
        return next((r for r in self.releases if r.version == version), None)

    def latest_release(self) -> ReleaseRecord | None:
        if self.latest is None:
            return None
        return self.find(self.latest)


@dataclass(slots=True)
class Manifest:
    """Per-tool manifest describing channels and their releases."""

    tool: str
    schema_version: int = SCHEMA_VERSION
    channels: dict[str, Channel] = field(default_factory=dict)

    def channel(self, name: str) -> Channel | None:
        return self.channels.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool": self.tool,
            "channels": {
                name: {
                    "latest": chan.latest,
                    "releases": [r.to_dict() for r in chan.releases],
                }
                for name, chan in self.channels.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        if not isinstance(data, dict):
            raise ManifestError("Manifest root must be a JSON object.")
        tool = data.get("tool")
        if not tool:
            raise ManifestError("Manifest missing required 'tool' field.")
        channels: dict[str, Channel] = {}
        for name, chan in data.get("channels", {}).items():
            releases = [ReleaseRecord.from_dict(r) for r in chan.get("releases", [])]
            channels[name] = Channel(latest=chan.get("latest"), releases=releases)
        return cls(
            tool=str(tool),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            channels=channels,
        )


def new_manifest(tool: str) -> Manifest:
    """Create an empty manifest for a tool."""
    return Manifest(tool=tool)


def read_manifest(path: Path) -> Manifest:
    """Read and parse a manifest JSON file."""
    path = Path(path)
    if not path.is_file():
        raise ManifestError(f"Manifest not found at {path}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Invalid JSON in manifest {path}: {exc}") from exc
    return Manifest.from_dict(data)


def write_manifest(path: Path, manifest: Manifest) -> None:
    """Write a manifest atomically (temp file + :func:`os.replace`)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=False)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name, suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with a trailing ``Z``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def add_release(manifest: Manifest, channel: str, release: ReleaseRecord) -> Manifest:
    """Upsert a release into a channel and refresh the ``latest`` pointer.

    Mutates and returns ``manifest``. An existing release with the same version is
    replaced. ``latest`` is set to the release with the highest version.
    """
    from drivedeploy.core import versioning

    chan = manifest.channels.setdefault(channel, Channel())
    chan.releases = [r for r in chan.releases if r.version != release.version]
    chan.releases.append(release)

    latest = chan.releases[0].version
    for record in chan.releases[1:]:
        if versioning.is_newer(record.version, latest):
            latest = record.version
    chan.latest = latest
    return manifest
