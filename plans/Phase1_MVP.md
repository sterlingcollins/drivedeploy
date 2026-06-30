# drivedeploy — Phase 1: MVP Plan

> **Status:** Draft for review — all Phase 0 decisions resolved.
> **Depends on:** `Phase0_Overview.md` (decisions §13.1, including D7a=generated
> module, D16=`release`, D17=`.zip`, D18=`win64`, D19=extract+helper-swap with an
> AV-safe staged fallback). No assumptions remain pending.
> **Goal:** Prove the full **publish → update** round-trip on a real
> UNC/SMB/mapped network drive, Windows-only, trusted share, checksums only.

---

## 1. Scope

### In scope
- Maintainer-side `publish()` (functional API).
- Client-side `check()` / `apply()` self-update for **Windows**, supporting both
  **one-file** and **one-dir** (archived) artifacts.
- JSON manifest read/write with atomic replace.
- Config loading from the tool's `[tool.drivedeploy]` + version resolution.
- Channel support with a single default channel (`release`) when unspecified (D16).
- SHA256 integrity verification.
- Rollback via explicit version re-download from the remote.
- PyInstaller freezer support behind a small interface (so other freezers slot in later).
- OS guards: raise `NotImplementedError` on non-Windows in the swap path.
- `change-log.md` at repo root.
- `tests/` with a temp-dir-backed "fake drive".

### Out of scope (Phase 2+)
- macOS/Linux self-replace, other freezers' implementations, distribution-level
  signing, manifest locking for concurrent publishers, retention/pruning, the Typer
  CLI extra (functional API only for MVP), synced cloud folders.

---

## 2. Proposed Package Layout

Following the user's import rules (functions in modules + namespace imports;
classes/exceptions via direct import) and "small, focused modules".

```
src/drivedeploy/
├── __init__.py                 # re-export functional entry points (publish, update)
├── errors.py                   # exception classes (direct-import)
├── core/
│   ├── __init__.py
│   ├── config.py               # load + validate [tool.drivedeploy]
│   ├── versioning.py           # resolve version (project/vcs/literal) + compare
│   ├── platforms.py            # platform tag derivation; OS guard helpers
│   ├── hashing.py              # sha256_file()
│   ├── manifest.py             # dataclasses + read_manifest/write_manifest (atomic)
│   └── layout.py               # paths on the drive (channel dirs, artifact names)
├── freezers/
│   ├── __init__.py
│   ├── base.py                 # Freezer protocol/interface (locate artifact, kind)
│   └── pyinstaller.py          # PyInstaller implementation
├── publish/
│   ├── __init__.py
│   ├── archive.py              # zip a one-dir bundle (D17)
│   ├── embed.py                # generate _drivedeploy_embed.py for the tool (D7a=B)
│   └── publisher.py            # publish(): orchestrate copy + manifest update
└── update/
    ├── __init__.py
    ├── client_config.py        # import generated _drivedeploy_embed module (D7a=B)
    ├── updater.py              # check(), apply(), rollback, finalize_pending()
    ├── download.py             # copy-from-drive to temp + verify checksum
    └── swap_windows.py         # live one-file/one-dir swap + AV-safe staged fallback
```

`__init__.py` re-exports the modules so callers do
`from drivedeploy import publish, update` and then `publish.publish(...)`.

---

## 3. Public API (target signatures)

```python
# drivedeploy/publish/publisher.py
def publish(
    project_dir: Path = Path("."),
    *,
    channel: Optional[str] = None,     # overrides config; None -> config/default
    version: Optional[str] = None,     # overrides resolved version
    dry_run: bool = False,
) -> ReleaseRecord: ...

# drivedeploy/update/updater.py
def check() -> Optional[UpdateInfo]:   # None if already current
    ...
def apply(
    *,
    version: Optional[str] = None,     # None -> latest in channel; set -> rollback/pin
    strategy: str = "auto",            # "auto" | "live" | "staged" (AV fallback, D19)
    relaunch: bool = True,
) -> None: ...

def finalize_pending() -> bool:        # apply a staged update on next launch; True if applied
    ...
```

The tool author calls `finalize_pending()` early at startup so a previously
**staged** update (AV-safe fallback) is swapped in before the app runs.

Supporting dataclasses live in `core/manifest.py` (`ReleaseRecord`, `Channel`,
`Manifest`) and `update/updater.py` (`UpdateInfo`). Exceptions in `errors.py`:
`DriveDeployError` (base), `ConfigError`, `ManifestError`, `IntegrityError`,
`UnsupportedPlatformError`, `ArtifactNotFoundError`.

---

## 4. Component Details

### 4.1 `core/config.py`
- Parse `pyproject.toml` with `tomllib` (stdlib, 3.14).
- Fields: `name` (default `[project].name`), `location`, `channel` (optional),
  `platform` (optional → derive), `artifact`, `kind` (`onefile`|`onedir`),
  `version_source` (`project`|`vcs`|literal).
- Validate: location non-empty; artifact path exists at publish time; `kind` valid.
- Return a frozen dataclass `DriveDeployConfig`.

### 4.2 `core/versioning.py`
- `resolve_version(config, project_dir)`:
  - `version_source == "project"` → read `[project].version`; if `version` is in
    `[project].dynamic`, fall back to VCS.
  - `version_source == "vcs"` → `git describe --tags --dirty` (via `subprocess`).
  - else treat the value as a literal version string.
- `is_newer(a, b)` using `packaging.version.Version` (add `packaging` dependency).

### 4.3 `core/platforms.py`
- `current_platform_tag()` → `win64` for MVP (D18).
- `ensure_windows()` → raise `UnsupportedPlatformError` (subclass of
  `NotImplementedError`) on non-Windows, used by `swap_windows`/`apply`.

### 4.4 `core/manifest.py`
- Dataclasses mirroring the §6 schema (`schema_version`, `tool`, `channels`).
- `read_manifest(path)` / `write_manifest(path, manifest)` — write temp + `os.replace`.
- `add_release(manifest, channel, release)` — upsert + refresh `latest`.

### 4.5 `core/layout.py`
- Given config + version + platform + kind, compute:
  - tool dir: `<location>/<name>/`
  - manifest path: `<tool>/manifest.json`
  - channel dir: `<tool>/<channel-or-default>/`
  - artifact filename: `<name>-<version>-<platform>.<ext>` (`.exe` | `.zip`).

### 4.6 `freezers/`
- `base.Freezer` protocol: `locate(config, project_dir) -> FrozenArtifact`
  (`path`, `kind`). `pyinstaller.py` resolves the `dist/` output per `kind`.
- Selection is implicit for MVP (PyInstaller only); interface keeps D14 open.

### 4.7 `publish/`
- `archive.zip_bundle(src_dir, dest_zip)` for one-dir (D17: stdlib `zipfile`).
- `embed.generate_embed_module(config, version, dest)` (D7a=B) — write
  `<tool>/_drivedeploy_embed.py` with the resolved client config baked in as
  constants (location, name, channel, kind, version, platform). The maintainer
  regenerates this before freezing; it is `.gitignore`d by default. (Functional API
  in MVP; the Typer extra will wrap it as `drivedeploy embed`.)
- `publisher.publish()` flow:
  1. Load config, resolve version + platform.
  2. Locate frozen artifact via freezer.
  3. If one-dir → zip to temp; compute sha256 + size.
  4. Copy artifact into the channel dir on the drive.
  5. Read-or-init manifest, `add_release`, write atomically.
  6. Return `ReleaseRecord`. (`dry_run` skips copy/write.)

### 4.8 `update/`
- `client_config.load()` (D7a=B) — `import drivedeploy_embed` style import of the
  generated `_drivedeploy_embed` module baked into the frozen tool, returning a
  `DriveDeployConfig`. Isolated here so an alternate embedding scheme would be a
  one-module change.
- `updater.check()` — load client config, read manifest, compare running version
  (from baked config) to channel `latest`; return `UpdateInfo` or `None`.
- `download.fetch(release, dest_dir)` — copy from drive, verify sha256
  (`IntegrityError` on mismatch).
- `updater.apply(version=...)` — resolve target release (latest or explicit for
  rollback), download+verify, dispatch to the configured swap strategy, optionally
  relaunch.
- `swap_windows` (pluggable strategy + AV-safe fallback, D19):
  - **live one-file:** rename running `.exe`→`.old`, move new in, relaunch, clean
    `.old` on next start.
  - **live one-dir:** extract zip to temp sibling, spawn helper, exit, helper swaps
    dir + relaunches.
  - **staged fallback:** when a live swap is disabled or fails (e.g. AV blocks it),
    stage the verified payload beside the install and write a pending-update marker;
    apply on next launch (and/or emit manual instructions / a generated script).
    `apply()` accepts a `strategy` hint (`auto` | `live` | `staged`).
  - `ensure_windows()` guard at entry; non-Windows raises `UnsupportedPlatformError`.

---

## 5. Dependencies

- Runtime: `packaging` (version comparison). Everything else stdlib (`tomllib`,
  `json`, `hashlib`, `zipfile`, `shutil`, `subprocess`, `pathlib`).
- Optional extra (NOT in MVP build, declared for later): `drivedeploy[typer]`.
- Dev group (`uv add --group dev`): `pytest`, `ruff`.
- Add via `uv add packaging` and `uv add --group dev pytest ruff`.

---

## 6. Testing Strategy (`tests/`)

One test file per module. Use a `tmp_path`-based **fake drive** fixture.
- `test_config.py` — parsing, defaults, validation errors.
- `test_versioning.py` — project/vcs/literal resolution, `is_newer` edge cases.
- `test_manifest.py` — round-trip read/write, atomic replace, `add_release`/`latest`.
- `test_layout.py` — path + filename construction (onefile/onedir, default channel).
- `test_hashing.py` — known-vector sha256.
- `test_publisher.py` — full publish into fake drive (onefile + onedir), dry-run.
- `test_download.py` — checksum pass/fail (`IntegrityError`).
- `test_updater.py` — `check()` newer/current/rollback selection (swap mocked).
- `test_embed.py` — generated `_drivedeploy_embed.py` is valid, importable, and
  round-trips to the same `DriveDeployConfig`.
- `test_platforms.py` — `ensure_windows()` raises off-Windows (monkeypatch).
- Swap logic: unit-test the planning/decision parts and the staged fallback
  (marker write + `finalize_pending()`); full live relaunch is integration and run
  manually on a Windows box with AV enabled for MVP.

---

## 7. Build / Tooling

- `ruff format` + `ruff check --fix` on all edited Python (honor `ruff.toml` if added).
- Keep `requires-python = ">=3.14"`; use modern syntax, `Optional[...]` not `| None`,
  builtin generics, `pathlib`.
- Update `[project.scripts]` only if/when the Typer extra lands (Phase 2-ish); MVP is
  functional-API-only, so the current `drivedeploy = "drivedeploy:main"` placeholder
  can stay for now.

---

## 8. Milestones / Task Order

1. **Scaffold + deps** — create package dirs, `errors.py`, add `packaging`,
   dev group; add `change-log.md`.
2. **Core** — `config`, `versioning`, `platforms`, `hashing`, `manifest`, `layout`
   (+ tests).
3. **Freezer interface** — `base` + `pyinstaller` (+ test against a fixture dist).
4. **Publish** — `archive`, `embed`, `publisher` (+ tests on fake drive).
5. **Update (logic)** — `client_config`, `download`, `updater.check/apply` selection
   (+ tests, swap mocked).
6. **Swap (Windows)** — `swap_windows`: live one-file → live one-dir → staged
   fallback + `finalize_pending()`; manual integration test with AV enabled.
7. **Round-trip demo** — script/manual: build a sample tool, publish, update, rollback,
   and exercise the staged fallback path.
8. **Docs** — update `README.md`, `change-log.md`; record any decision changes back
   into `Phase0_Overview.md`.

---

## 9. Acceptance Criteria (Definition of Done)

- `publish()` places a correctly-named artifact + valid `manifest.json` on a real
  mapped/UNC drive for both `onefile` and `onedir`.
- A frozen sample tool can `check()` and detect a newer version, `apply()` it, and
  relaunch into the new version on Windows.
- `apply(version="<older>")` performs a rollback by re-downloading from the remote.
- `apply(strategy="staged")` (and the auto-fallback when a live swap is blocked)
  stages the update and `finalize_pending()` applies it on next launch.
- Checksum mismatch raises `IntegrityError` and aborts the swap.
- Non-Windows raises `NotImplementedError`/`UnsupportedPlatformError` in the swap path.
- `ruff check` and `ruff format` clean; `pytest` green.

---

## 10. Resolved Inputs & Empirical Risks

All Phase 0 decisions are resolved (`Phase0_Overview.md` §13.1):
- **D7a** — client config via **generated module** (`_drivedeploy_embed.py`).
- **D16** — default channel name **`release`**.
- **D17** — one-dir archive format **`.zip`**.
- **D18** — MVP platform tag **`win64`**.
- **D19** — one-dir update = extract + helper-swap dir, **plus an AV-safe staged
  fallback** applied via `finalize_pending()`.

The remaining unknowns are **empirical, not strategic**, and are handled as build
tasks rather than blockers:
- Validate the live one-file and one-dir swaps on real Windows + antivirus; confirm
  the staged fallback triggers cleanly when a live swap is blocked.
- Confirm directory-rename behavior while the bundled exe is in use (informs whether
  the helper waits for full process exit before swapping).

Nothing blocks starting on the **core** modules (§8 steps 1–2); the live-swap
validation can proceed in parallel once the updater logic exists.
