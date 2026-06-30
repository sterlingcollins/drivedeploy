"""Platform tag derivation and OS guards.

MVP targets Windows only (Phase 0 decisions D2/D18). The platform tag is ``win64``.
"""

from __future__ import annotations

import sys

from drivedeploy.errors import UnsupportedPlatformError

WINDOWS_PLATFORM_TAG = "win64"


def current_platform_tag() -> str:
    """Return the platform tag for the current build host.

    For the MVP this is always ``win64`` (D18). Cross-platform tags are a later phase.
    """
    return WINDOWS_PLATFORM_TAG


def is_windows() -> bool:
    """Return True when running on Windows."""
    return sys.platform.startswith("win")


def ensure_windows() -> None:
    """Raise :class:`UnsupportedPlatformError` when not on Windows.

    Used to guard the self-replace / swap path, which is Windows-only for the MVP.
    """
    if not is_windows():
        raise UnsupportedPlatformError(
            f"drivedeploy self-update is Windows-only for the MVP; "
            f"current platform is {sys.platform!r}."
        )
