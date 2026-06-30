"""Windows self-replace: live one-file/one-dir swaps + AV-safe staged fallback (D19).

Strategy is pluggable (Phase 0 decision D19):

* **live one-file** — rename the running ``.exe`` to ``.old``, move the new exe in,
  relaunch, and delete ``.old`` on the next start.
* **live one-dir** — extract the bundle beside the install, spawn a helper, exit, and
  let the helper swap the directory and relaunch.
* **staged fallback** — when a live swap is disabled or fails (e.g. antivirus blocks
  it), stage the verified payload beside the install and write a pending-update
  marker; :func:`finalize_pending` applies it on the next launch.

The live relaunch/helper paths guard with :func:`ensure_windows`. The staging and
marker file operations are plain filesystem work so they remain testable anywhere.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from drivedeploy.core import manifest
from drivedeploy.core.platforms import ensure_windows, is_windows
from drivedeploy.publish import archive

PENDING_MARKER_NAME = ".drivedeploy_pending.json"
STAGE_DIR_NAME = ".drivedeploy_staged"
OLD_SUFFIX = ".old"

VALID_STRATEGIES = ("auto", "live", "staged")


@dataclass(frozen=True, slots=True)
class PendingUpdate:
    """A staged update awaiting application on the next launch."""

    version: str
    kind: str
    staged_path: str
    target_path: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PendingUpdate:
        return cls(
            version=str(data["version"]),
            kind=str(data["kind"]),
            staged_path=str(data["staged_path"]),
            target_path=str(data["target_path"]),
            created_at=str(data["created_at"]),
        )


def current_executable() -> Path:
    """Path to the running executable (the frozen tool at runtime)."""
    return Path(sys.executable)


def plan_swap(strategy: str, kind: str) -> str:
    """Decide the initial swap mode for a strategy.

    Returns ``"live"`` or ``"staged"``. ``auto`` prefers a live swap (callers fall
    back to staged if it fails). Raises ``ValueError`` on an unknown strategy/kind.
    """
    if strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"strategy must be one of {VALID_STRATEGIES}, got {strategy!r}."
        )
    if kind not in ("onefile", "onedir"):
        raise ValueError(f"Unknown artifact kind: {kind!r}.")
    if strategy == "staged":
        return "staged"
    return "live"


# --- pending marker -------------------------------------------------------------


def marker_path(install_dir: Path) -> Path:
    """Path to the pending-update marker for an install directory."""
    return Path(install_dir) / PENDING_MARKER_NAME


def write_pending(install_dir: Path, pending: PendingUpdate) -> Path:
    """Write the pending-update marker atomically."""
    path = marker_path(install_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(pending.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def read_pending(install_dir: Path) -> PendingUpdate | None:
    """Read the pending-update marker, or ``None`` when absent/unreadable."""
    path = marker_path(install_dir)
    if not path.is_file():
        return None
    try:
        return PendingUpdate.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError, KeyError, TypeError:
        return None


def clear_pending(install_dir: Path) -> None:
    """Remove the pending-update marker if present."""
    marker_path(install_dir).unlink(missing_ok=True)


# --- staging --------------------------------------------------------------------


def stage_update(
    install_dir: Path,
    downloaded: Path,
    *,
    kind: str,
    version: str,
    target_path: Path,
) -> PendingUpdate:
    """Stage a verified payload beside the install and write the pending marker.

    For ``onefile`` the downloaded exe is copied into the stage dir; for ``onedir``
    the downloaded ``.zip`` is extracted into the stage dir. Returns the
    :class:`PendingUpdate` that was recorded.
    """
    install_dir = Path(install_dir)
    stage_root = install_dir / STAGE_DIR_NAME
    if stage_root.exists():
        shutil.rmtree(stage_root, ignore_errors=True)
    stage_root.mkdir(parents=True, exist_ok=True)

    if kind == "onedir":
        staged = stage_root / "bundle"
        archive.extract_bundle(downloaded, staged)
    else:
        staged = stage_root / Path(target_path).name
        shutil.copy2(downloaded, staged)

    pending = PendingUpdate(
        version=version,
        kind=kind,
        staged_path=str(staged),
        target_path=str(target_path),
        created_at=manifest.utc_now_iso(),
    )
    write_pending(install_dir, pending)
    return pending


# --- in-place swaps -------------------------------------------------------------


def cleanup_old_onefile(target_exe: Path) -> None:
    """Delete a leftover ``.old`` file from a previous one-file swap."""
    old = Path(str(target_exe) + OLD_SUFFIX)
    old.unlink(missing_ok=True)


def swap_onefile_inplace(target_exe: Path, new_exe: Path) -> Path:
    """Replace ``target_exe`` with ``new_exe`` by renaming the old aside.

    Works even when ``target_exe`` is the running process (Windows allows renaming a
    running exe). Returns the path of the renamed ``.old`` file.
    """
    target_exe = Path(target_exe)
    old = Path(str(target_exe) + OLD_SUFFIX)
    old.unlink(missing_ok=True)
    os.replace(target_exe, old)
    os.replace(new_exe, target_exe)
    return old


def swap_onedir_inplace(target_dir: Path, new_dir: Path) -> None:
    """Replace ``target_dir`` contents with ``new_dir`` via an aside-and-move.

    Not safe to call while an exe inside ``target_dir`` is running; the live one-dir
    path uses a helper process for that. Used by :func:`finalize_pending`.
    """
    target_dir = Path(target_dir)
    backup = Path(str(target_dir) + OLD_SUFFIX)
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    if target_dir.exists():
        os.replace(target_dir, backup)
    os.replace(new_dir, target_dir)
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def relaunch(exe: Path, args: list[str] | None = None) -> None:
    """Spawn ``exe`` detached and exit the current process (Windows only)."""
    ensure_windows()
    subprocess.Popen([str(exe), *(args or [])], close_fds=True)
    raise SystemExit(0)


# --- live entry points ----------------------------------------------------------


def swap_onefile_live(
    target_exe: Path, new_exe: Path, *, relaunch_after: bool = True
) -> None:
    """Live one-file swap (rename running exe, move new in, relaunch)."""
    ensure_windows()
    swap_onefile_inplace(target_exe, new_exe)
    if relaunch_after:
        relaunch(target_exe)


def _write_onedir_helper(
    helper_path: Path, *, pid: int, staged_dir: Path, target_dir: Path, exe: Path
) -> Path:
    """Write a small batch helper that waits for exit, swaps the dir, relaunches."""
    script = (
        "@echo off\r\n"
        "setlocal\r\n"
        f":wait\r\n"
        f'tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >NUL\r\n"
        "  goto wait\r\n"
        ")\r\n"
        f'rmdir /S /Q "{target_dir}{OLD_SUFFIX}" 2>NUL\r\n'
        f'move "{target_dir}" "{target_dir}{OLD_SUFFIX}" >NUL\r\n'
        f'move "{staged_dir}" "{target_dir}" >NUL\r\n'
        f'rmdir /S /Q "{target_dir}{OLD_SUFFIX}" 2>NUL\r\n'
        f'start "" "{exe}"\r\n'
    )
    helper_path.write_text(script, encoding="utf-8")
    return helper_path


def swap_onedir_live(
    target_dir: Path,
    staged_dir: Path,
    exe: Path,
    *,
    relaunch_after: bool = True,
) -> None:
    """Live one-dir swap via a helper process that runs after this process exits."""
    ensure_windows()
    target_dir = Path(target_dir)
    helper = target_dir.parent / "_drivedeploy_swap.bat"
    _write_onedir_helper(
        helper,
        pid=os.getpid(),
        staged_dir=Path(staged_dir),
        target_dir=target_dir,
        exe=Path(exe),
    )
    subprocess.Popen(["cmd", "/c", str(helper)], close_fds=True)
    if relaunch_after:
        raise SystemExit(0)


# --- finalize (apply a staged update at startup) --------------------------------


def _candidate_install_dirs() -> list[Path]:
    """Where a marker might live: the exe's dir (onefile) or its parent (onedir)."""
    exe = current_executable()
    return [exe.parent, exe.parent.parent]


def finalize_pending(
    install_dir: Path | None = None, *, relaunch_after: bool = True
) -> bool:
    """Apply a previously staged update on launch. Returns True if one was applied.

    Called early at startup by the tool. When ``install_dir`` is omitted, the marker
    is searched for beside the exe (onefile) and one level up (onedir). The file-swap
    itself is plain filesystem work; relaunching is Windows-only and skipped elsewhere.
    """
    if install_dir is not None:
        candidates = [Path(install_dir)]
    else:
        candidates = _candidate_install_dirs()

    install_dir = next((d for d in candidates if read_pending(d) is not None), None)
    if install_dir is None:
        return False

    pending = read_pending(install_dir)
    if pending is None:
        return False

    staged = Path(pending.staged_path)
    target = Path(pending.target_path)

    if pending.kind == "onedir":
        swap_onedir_inplace(target, staged)
    else:
        swap_onefile_inplace(target, staged)

    clear_pending(install_dir)
    shutil.rmtree(install_dir / STAGE_DIR_NAME, ignore_errors=True)

    if relaunch_after and is_windows():
        relaunch(target)
    return True
