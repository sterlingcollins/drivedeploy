"""Exception hierarchy for drivedeploy.

These are imported directly (per the project import rules for classes/exceptions),
e.g. ``from drivedeploy.errors import ConfigError``.
"""


class DriveDeployError(Exception):
    """Base class for all drivedeploy errors."""


class ConfigError(DriveDeployError):
    """Raised when ``[tool.drivedeploy]`` config is missing or invalid."""


class ManifestError(DriveDeployError):
    """Raised when a manifest cannot be read, parsed, or is malformed."""


class IntegrityError(DriveDeployError):
    """Raised when a downloaded artifact fails checksum verification."""


class UnsupportedPlatformError(DriveDeployError, NotImplementedError):
    """Raised when an operation is attempted on an unsupported OS.

    Subclasses :class:`NotImplementedError` so callers that guard on the stdlib
    exception type still catch it (Phase 0 decision D2).
    """


class ArtifactNotFoundError(DriveDeployError):
    """Raised when an expected frozen artifact or release file is missing."""
