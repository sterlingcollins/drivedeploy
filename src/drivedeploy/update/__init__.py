"""Client-side self-update: client_config, download, updater, swap_windows."""

from drivedeploy.update.updater import UpdateInfo, apply, check, finalize_pending

__all__ = ["UpdateInfo", "apply", "check", "finalize_pending"]
