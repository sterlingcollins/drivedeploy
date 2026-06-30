"""Path and filename construction for artifacts on the shared drive (§4.5).

Layout::

    <location>/<name>/manifest.json
    <location>/<name>/<channel>/<name>-<version>-<platform>.<ext>

``<ext>`` is ``exe`` for one-file builds and ``zip`` for archived one-dir builds.
Manifest ``filename`` entries are stored channel-relative (e.g.
``release/mytool-1.4.0-win64.exe``) with forward slashes.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

MANIFEST_NAME = "manifest.json"
_EXT_BY_KIND = {"onefile": "exe", "onedir": "zip"}


def artifact_extension(kind: str) -> str:
    """Return the artifact file extension (without dot) for an artifact kind."""
    try:
        return _EXT_BY_KIND[kind]
    except KeyError:
        raise ValueError(f"Unknown artifact kind: {kind!r}") from None


def tool_dir(location: str, name: str) -> Path:
    """Directory hosting a single tool's manifest + channels."""
    return Path(location) / name


def manifest_path(location: str, name: str) -> Path:
    """Absolute path to a tool's manifest on the drive."""
    return tool_dir(location, name) / MANIFEST_NAME


def channel_dir(location: str, name: str, channel: str) -> Path:
    """Absolute path to a channel directory on the drive."""
    return tool_dir(location, name) / channel


def artifact_filename(name: str, version: str, platform: str, kind: str) -> str:
    """Build the bare artifact filename (no channel prefix)."""
    ext = artifact_extension(kind)
    return f"{name}-{version}-{platform}.{ext}"


def artifact_relpath(channel: str, filename: str) -> str:
    """Channel-relative POSIX path stored in the manifest's ``filename`` field."""
    return str(PurePosixPath(channel) / filename)


def artifact_path_for_release(location: str, name: str, filename: str) -> Path:
    """Absolute path on the drive for a manifest ``filename`` (channel-relative)."""
    return tool_dir(location, name) / PurePosixPath(filename)
