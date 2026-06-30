# Change Log

All notable changes to **drivedeploy** are recorded here. Newest entries on top.

## [Unreleased]

### Added — Phase 1 MVP

Initial implementation of the publish → update round-trip for frozen Python tools
distributed over a shared network drive (Windows-only behavior, trusted share,
checksums only). See `plans/Phase1_MVP.md`.

- **Core** (`drivedeploy.core`):
  - `config` — load + validate `[tool.drivedeploy]` from `pyproject.toml`.
  - `versioning` — resolve version (project/vcs/literal) and compare with `packaging`.
  - `platforms` — `win64` platform tag + `ensure_windows()` OS guard.
  - `hashing` — `sha256_file()`.
  - `manifest` — JSON manifest dataclasses + atomic read/write + `add_release`.
  - `layout` — drive paths and artifact filename construction.
- **Freezers** (`drivedeploy.freezers`): `Freezer` protocol + PyInstaller impl.
- **Publish** (`drivedeploy.publish`): `archive` (zip one-dir), `embed` (generated
  `_drivedeploy_embed.py`), `publisher.publish()`.
- **Update** (`drivedeploy.update`): `client_config`, `download` (copy + verify),
  `updater.check()/apply()/finalize_pending()`, `swap_windows` (live one-file,
  live one-dir helper swap, AV-safe staged fallback).
- **Errors** (`drivedeploy.errors`): `DriveDeployError`, `ConfigError`,
  `ManifestError`, `IntegrityError`, `UnsupportedPlatformError`, `ArtifactNotFoundError`.
- Tests in `tests/` over a temp-dir-backed fake drive (94 tests, all green).
- `examples/round_trip_demo.py` — runnable publish → check → apply (staged) →
  `finalize_pending` → rollback round-trip over a fake drive.
- Project tooling: `packaging` runtime dep, `pytest`/`ruff` dev group, `ruff.toml`,
  `README.md` usage guide, `_drivedeploy_embed.py` added to `.gitignore`.

Live one-file/one-dir swaps with real relaunch + antivirus remain a manual Windows
integration step (Phase 1 milestone 6); all decision/staging logic is unit-tested.
