"""Load the baked-in client config from the generated embed module (D7a = B).

Isolated here so an alternate embedding scheme would be a one-module change. The
frozen tool ships ``_drivedeploy_embed`` (see :mod:`drivedeploy.publish.embed`);
this module imports it and reconstructs a :class:`DriveDeployConfig` plus the
running version.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType

from drivedeploy.core.config import DriveDeployConfig
from drivedeploy.errors import ConfigError
from drivedeploy.publish.embed import EMBED_MODULE_NAME


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """The deployment config plus the running version baked into the tool."""

    config: DriveDeployConfig
    version: str


def from_module(module: ModuleType) -> ClientConfig:
    """Reconstruct a :class:`ClientConfig` from a loaded embed module."""
    try:
        config = DriveDeployConfig(
            name=module.NAME,
            location=module.LOCATION,
            channel=module.CHANNEL,
            platform=module.PLATFORM,
            artifact=module.ARTIFACT,
            kind=module.KIND,
            version_source=module.VERSION_SOURCE,
        )
        return ClientConfig(config=config, version=module.VERSION)
    except AttributeError as exc:
        raise ConfigError(f"Embed module is missing required attribute: {exc}") from exc


def load(module_name: str = EMBED_MODULE_NAME) -> ClientConfig:
    """Import the generated embed module by name and return the client config."""
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(
            f"Could not import embed module {module_name!r}; was it generated and "
            f"frozen into the tool? ({exc})"
        ) from exc
    return from_module(module)
