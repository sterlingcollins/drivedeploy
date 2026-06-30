"""End-to-end round-trip demo over a temp fake drive (no real freezer needed).

Exercises the full publish -> check -> apply (staged) -> finalize -> rollback flow
using the staged strategy so it runs on any OS. Run it with::

    uv run python examples/round_trip_demo.py

The live one-file/one-dir swaps with real relaunch are validated separately on a
Windows box (see plans/Phase1_MVP.md milestone 6).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.publish import publisher
from drivedeploy.update import swap_windows, updater
from drivedeploy.update.client_config import ClientConfig


def _make_project(root: Path, drive: Path, version: str) -> Path:
    project = root / f"proj-{version}"
    (project / "dist").mkdir(parents=True)
    (project / "dist" / "mytool.exe").write_bytes(f"MZ exe payload {version}".encode())
    (project / "pyproject.toml").write_text(
        f'[project]\nname = "mytool"\nversion = "{version}"\n\n'
        f"[tool.drivedeploy]\nlocation = {str(drive)!r}\n"
        'kind = "onefile"\nartifact = "dist/mytool.exe"\n',
        encoding="utf-8",
    )
    return project


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="drivedeploy-demo-") as tmp:
        root = Path(tmp)
        drive = root / "drive"
        drive.mkdir()

        print(f"Fake drive: {drive}")

        # --- maintainer publishes two versions ---------------------------------
        publisher.publish(_make_project(root, drive, "1.0.0"))
        rec = publisher.publish(_make_project(root, drive, "1.1.0"))
        print(f"Published 1.0.0 and {rec.version} ({rec.filename})")

        # --- simulate an installed v1.0.0 tool ---------------------------------
        install = root / "install"
        install.mkdir()
        exe = install / "mytool.exe"
        exe.write_bytes(b"MZ exe payload 1.0.0")
        swap_windows.current_executable = lambda: exe  # point swap at the fake install

        client = ClientConfig(
            config=DriveDeployConfig(name="mytool", location=str(drive)),
            version="1.0.0",
        )

        # --- check + staged apply + finalize -----------------------------------
        info = updater.check(client=client)
        print(f"check(): update available -> {info.latest_version}")

        mode = updater.apply(strategy="staged", client=client)
        print(f"apply(strategy='staged') -> {mode}; pending marker written")

        applied = swap_windows.finalize_pending(install, relaunch_after=False)
        print(f"finalize_pending() -> applied={applied}; exe now: {exe.read_bytes()!r}")

        # --- rollback to 1.0.0 -------------------------------------------------
        client_now = ClientConfig(config=client.config, version="1.1.0")
        updater.apply(version="1.0.0", strategy="staged", client=client_now)
        swap_windows.finalize_pending(install, relaunch_after=False)
        print(f"rollback to 1.0.0 -> exe now: {exe.read_bytes()!r}")

        print("Round-trip demo complete.")


if __name__ == "__main__":
    main()
