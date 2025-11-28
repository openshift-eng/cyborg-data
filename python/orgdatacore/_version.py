"""Version information for orgdatacore.

This module provides semantic versioning information for the library.
Version follows SemVer 2.0.0 (https://semver.org/).

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

from typing import Final

# Version components
VERSION_MAJOR: Final[int] = 1
VERSION_MINOR: Final[int] = 0
VERSION_PATCH: Final[int] = 0

# Pre-release suffix (empty for stable releases)
# Examples: "alpha.1", "beta.2", "rc.1", ""
VERSION_PRERELEASE: Final[str] = ""

# Build metadata (optional, not part of version comparison)
VERSION_BUILD: Final[str] = ""

# Computed version strings
__version_info__: Final[tuple[int, int, int]] = (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)


def _compute_version() -> str:
    """Compute the full version string."""
    version = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
    if VERSION_PRERELEASE:
        version = f"{version}-{VERSION_PRERELEASE}"
    if VERSION_BUILD:
        version = f"{version}+{VERSION_BUILD}"
    return version


__version__: Final[str] = _compute_version()


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
    return {
        "version": __version__,
        "version_info": __version_info__,
        "api_version": API_VERSION,
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH,
        "prerelease": VERSION_PRERELEASE,
        "build": VERSION_BUILD,
    }

