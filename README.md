# drivedeploy

Server-less distribution of **frozen Python tools** over a shared network drive.

Teams in restricted / air-gapped environments often have no internal PyPI mirror,
no internet, and no permission to run servers — but they almost always have a
**shared network location** (a mapped drive or UNC/SMB path). `drivedeploy` turns
that humble folder into a lightweight distribution channel with two halves:

- **Publish side** (maintainer): push a frozen executable to the share with a
  versioned JSON manifest.
- **Pull side** (bundled in the tool): a self-update that reads the manifest and
  swaps the running tool in place.

> **Status:** Phase 1 MVP — Windows-only behavior, trusted share, checksums only.
> See `plans/Phase1_MVP.md` and `plans/Phase0_Overview.md` for the full design.

## Install (maintainer)

```bash
uv add drivedeploy           # runtime
# optional ready-made CLI (Phase 2+): uv add "drivedeploy[typer]"
```

## Configure the tool

Add a `[tool.drivedeploy]` table to the **consuming tool's** `pyproject.toml`:

```toml
[tool.drivedeploy]
name = "mytool"                            # default: [project].name
location = "\\\\share\\tools\\drivedeploy"  # UNC / SMB / mapped drive root
channel = "stable"                          # optional; omit -> "release"
platform = "win64"                          # optional; derived if omitted
artifact = "dist/mytool.exe"                # frozen output (file=onefile, dir=onedir)
kind = "onefile"                            # "onefile" | "onedir"
version_source = "project"                  # "project" | "vcs" | "<literal>"
```

## Publish (maintainer)

```python
from drivedeploy import publish

# 1. Freeze the tool (PyInstaller) so `artifact` exists.
# 2. Generate the baked-in client config and freeze it into the tool:
from drivedeploy.publish import embed
from drivedeploy.core import config, versioning
cfg = config.load_config(".")
embed.generate_embed_module(cfg, versioning.resolve_version(cfg, "."), "src/mytool")

# 3. Publish the artifact + manifest to the drive:
record = publish.publish(project_dir=".")
print(record.version, record.filename)
```

`publish()` archives one-dir bundles to `.zip`, copies the artifact into the
channel directory, computes its SHA256, and updates `manifest.json` atomically.

## Self-update (bundled in the tool)

```python
from drivedeploy import update

# Early at startup: apply a previously staged update, if any.
update.finalize_pending()

info = update.check()           # None if already current
if info:
    update.apply()              # download, verify, swap, relaunch

# Rollback to an older version (re-downloaded from the remote):
update.apply(version="1.3.0")

# Force the AV-safe staged path (applied on next launch):
update.apply(strategy="staged")
```

`apply(strategy=...)` accepts `"auto"` (live swap, falling back to staged if the
live swap is blocked), `"live"`, or `"staged"`.

## Self-update mechanics (Windows)

- **one-file:** rename the running `.exe` → `.old`, move the new exe in, relaunch,
  delete `.old` on next start.
- **one-dir:** extract the `.zip` beside the install, spawn a helper, exit, let the
  helper swap the directory and relaunch.
- **staged fallback (D19):** when a live swap is disabled or blocked (e.g. by
  antivirus), the verified payload is staged beside the install with a pending
  marker; `finalize_pending()` applies it on the next launch.

Non-Windows raises `NotImplementedError` / `UnsupportedPlatformError` in the swap
path (cross-platform self-replace is Phase 3).

## Development

```bash
uv sync
uv run ruff format . && uv run ruff check .
uv run pytest
```

The live one-file/one-dir swaps with real relaunch and antivirus are validated
manually on Windows; everything else (planning, staging, `finalize_pending`, the
full publish → check → apply selection) is covered by the test suite over a
temp-dir-backed fake drive.

## License

See `LICENSE`.
