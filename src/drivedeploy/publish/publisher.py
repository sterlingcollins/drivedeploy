"""``publish()`` — orchestrate freeze location, archive, copy, and manifest update."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from drivedeploy.core import config as config_mod
from drivedeploy.core import hashing, layout, manifest, versioning
from drivedeploy.core.manifest import ReleaseRecord
from drivedeploy.freezers import pyinstaller
from drivedeploy.publish import archive


def publish(
    project_dir: Path = Path("."),
    *,
    channel: str | None = None,
    version: str | None = None,
    dry_run: bool = False,
    notes: str | None = None,
) -> ReleaseRecord:
    """Publish a frozen tool's artifact + manifest entry to the shared drive.

    ``channel`` and ``version`` override config/resolution when given. ``dry_run``
    computes the :class:`ReleaseRecord` without copying the artifact or writing the
    manifest.
    """
    project_dir = Path(project_dir)
    cfg = config_mod.load_config(project_dir)

    resolved_channel = channel or cfg.effective_channel()
    resolved_platform = cfg.effective_platform()
    resolved_version = version or versioning.resolve_version(cfg, project_dir)

    frozen = pyinstaller.locate(cfg, project_dir)

    filename = layout.artifact_filename(
        cfg.name, resolved_version, resolved_platform, cfg.kind
    )
    rel_filename = layout.artifact_relpath(resolved_channel, filename)

    with tempfile.TemporaryDirectory(prefix="drivedeploy-publish-") as tmp:
        if cfg.kind == "onedir":
            staged = archive.zip_bundle(frozen.path, Path(tmp) / filename)
        else:
            staged = Path(tmp) / filename
            shutil.copy2(frozen.path, staged)

        sha256 = hashing.sha256_file(staged)
        size = staged.stat().st_size

        record = ReleaseRecord(
            version=resolved_version,
            platform=resolved_platform,
            kind=cfg.kind,
            filename=rel_filename,
            sha256=sha256,
            size=size,
            published_at=manifest.utc_now_iso(),
            notes=notes,
        )

        if dry_run:
            return record

        dest = layout.channel_dir(cfg.location, cfg.name, resolved_channel) / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged, dest)

    manifest_path = layout.manifest_path(cfg.location, cfg.name)
    if manifest_path.is_file():
        current = manifest.read_manifest(manifest_path)
    else:
        current = manifest.new_manifest(cfg.name)
    manifest.add_release(current, resolved_channel, record)
    manifest.write_manifest(manifest_path, current)

    return record
