"""Version information for orgdatacore.

This module provides semantic versioning information for the library.
Version follows SemVer 2.0.0 (https://semver.org/).

The version is read from the installed package metadata (pyproject.toml).

API Compatibility:
- MAJOR version: Breaking changes to public API
- MINOR version: New features, backwards compatible
- PATCH version: Bug fixes, backwards compatible

Example:
    from orgdatacore import __version__, __version_info__

    print(f"orgdatacore v{__version__}")
    # orgdatacore v1.0.0

    major, minor, patch = __version_info__
    if major >= 1:
        # Use v1 features
        ...
"""

from importlib.metadata import version as get_pkg_version
from typing import Final


def _get_version() -> str:
    """Get version from package metadata (single source of truth: pyproject.toml)."""
    try:
        return get_pkg_version("orgdatacore")
    except Exception:
        # Fallback for development/editable installs where package isn't installed
        return "0.0.0.dev0"


__version__: Final[str] = _get_version()


def _parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch tuple."""
    # Handle pre-release suffixes like "1.0.0a1" or "1.0.0-beta.1"
    base_version = version_str.split("-")[0].split("+")[0]
    # Remove any alpha/beta/rc suffixes
    for suffix in ("a", "b", "rc", "dev"):
        if suffix in base_version:
            base_version = base_version.split(suffix)[0]

    parts = base_version.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


# Computed version tuple
__version_info__: Final[tuple[int, int, int]] = _parse_version(__version__)

# API version for compatibility checking
# This may differ from package version for API stability
API_VERSION: Final[str] = "1.0"


def check_api_compatibility(required_version: str) -> bool:
    """Check if this library version is compatible with the required API version.

    Uses semantic versioning rules:
    - Major version must match exactly
    - Library minor version must be >= required minor version

    Args:
        required_version: Required API version string (e.g., "1.0")

    Returns:
        True if compatible, False otherwise.

    Example:
        if not check_api_compatibility("1.0"):
            raise RuntimeError("Incompatible orgdatacore version")
    """
    try:
        req_parts = required_version.split(".")
        req_major = int(req_parts[0])
        req_minor = int(req_parts[1]) if len(req_parts) > 1 else 0

        api_parts = API_VERSION.split(".")
        api_major = int(api_parts[0])
        api_minor = int(api_parts[1]) if len(api_parts) > 1 else 0

        # Major must match, minor must be >= required
        return api_major == req_major and api_minor >= req_minor
    except (ValueError, IndexError):
        return False


def get_version_dict() -> dict[str, str | int | tuple[int, int, int]]:
    """Get version information as a dictionary.

    Useful for debugging and logging.

    Returns:
        Dictionary with version components.
    """
    major, minor, patch = __version_info__
    return {
        "version": __version__,
        "version_info": __version_info__,
        "api_version": API_VERSION,
        "major": major,
        "minor": minor,
        "patch": patch,
    }
