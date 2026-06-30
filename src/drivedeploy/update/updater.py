"""Client self-update orchestration: check(), apply(), finalize_pending()."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from drivedeploy.core import layout, manifest, versioning
from drivedeploy.core.manifest import ReleaseRecord
from drivedeploy.errors import ArtifactNotFoundError, ManifestError
from drivedeploy.update import client_config, download, swap_windows
from drivedeploy.update.client_config import ClientConfig
from drivedeploy.update.swap_windows import finalize_pending  # re-export


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """Describes an available update relative to the running version."""

    current_version: str
    latest_version: str
    channel: str
    release: ReleaseRecord


def _load_client(client: ClientConfig | None) -> ClientConfig:
    return client if client is not None else client_config.load()


def _read_channel_manifest(client: ClientConfig):
    cfg = client.config
    path = layout.manifest_path(cfg.location, cfg.name)
    man = manifest.read_manifest(path)
    channel_name = cfg.effective_channel()
    channel = man.channel(channel_name)
    if channel is None:
        raise ManifestError(
            f"Channel {channel_name!r} not present in manifest for {cfg.name!r}."
        )
    return channel_name, channel


def check(client: ClientConfig | None = None) -> UpdateInfo | None:
    """Return :class:`UpdateInfo` when a newer release exists, else ``None``."""
    client = _load_client(client)
    channel_name, channel = _read_channel_manifest(client)

    latest = channel.latest_release()
    if latest is None:
        return None
    if not versioning.is_newer(latest.version, client.version):
        return None

    return UpdateInfo(
        current_version=client.version,
        latest_version=latest.version,
        channel=channel_name,
        release=latest,
    )


def _resolve_target(channel, version: str | None) -> ReleaseRecord:
    if version is None:
        release = channel.latest_release()
        if release is None:
            raise ArtifactNotFoundError("No releases available in channel.")
        return release
    release = channel.find(version)
    if release is None:
        raise ArtifactNotFoundError(f"Version {version!r} not found in channel.")
    return release


def _swap_target(client: ClientConfig, kind: str) -> Path:
    exe = swap_windows.current_executable()
    return exe if kind == "onefile" else exe.parent


def apply(
    *,
    version: str | None = None,
    strategy: str = "auto",
    relaunch: bool = True,
    client: ClientConfig | None = None,
) -> str:
    """Download, verify, and apply a release; return the swap mode used.

    ``version`` selects an explicit release (rollback/pin); ``None`` means the
    channel's latest. ``strategy`` is ``auto`` | ``live`` | ``staged`` (D19). Returns
    ``"live"`` or ``"staged"`` describing how the update was applied.
    """
    client = _load_client(client)
    _, channel = _read_channel_manifest(client)
    release = _resolve_target(channel, version)

    kind = release.kind
    target = _swap_target(client, kind)
    mode = swap_windows.plan_swap(strategy, kind)

    with tempfile.TemporaryDirectory(prefix="drivedeploy-update-") as tmp:
        downloaded = download.fetch(client.config, release, Path(tmp))

        if mode == "staged":
            swap_windows.stage_update(
                _install_dir(target, kind),
                downloaded,
                kind=kind,
                version=release.version,
                target_path=target,
            )
            return "staged"

        try:
            _live_swap(target, downloaded, kind, relaunch)
            return "live"
        except OSError:
            if strategy == "live":
                raise
            swap_windows.stage_update(
                _install_dir(target, kind),
                downloaded,
                kind=kind,
                version=release.version,
                target_path=target,
            )
            return "staged"


def _install_dir(target: Path, kind: str) -> Path:
    """Directory that holds the marker/stage area (beside the exe or the bundle)."""
    return target.parent


def _live_swap(target: Path, downloaded: Path, kind: str, relaunch: bool) -> None:
    if kind == "onefile":
        swap_windows.swap_onefile_live(target, downloaded, relaunch_after=relaunch)
        return
    # Extract beside the install so the helper can swap it after this process exits.
    staged = target.parent / (target.name + ".new")
    if staged.exists():
        swap_windows.shutil.rmtree(staged, ignore_errors=True)
    swap_windows.archive.extract_bundle(downloaded, staged)
    exe = target / swap_windows.current_executable().name
    swap_windows.swap_onedir_live(target, staged, exe, relaunch_after=relaunch)


__all__ = ["UpdateInfo", "check", "apply", "finalize_pending"]
