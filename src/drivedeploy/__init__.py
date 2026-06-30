"""drivedeploy — server-less distribution of frozen Python tools over a shared drive.

Public surface is a functional API (Phase 0 decision D11):

    from drivedeploy import publish, update

    publish.publish(project_dir=".")   # maintainer side
    update.check()                     # is a newer version available?
    update.apply()                     # download, verify, swap, relaunch
"""

from drivedeploy import publish, update

__all__ = ["publish", "update", "main"]


def main() -> None:
    print(
        "drivedeploy: functional API only for the MVP. "
        "See `from drivedeploy import publish, update`."
    )
