"""Tests for version information."""

import re

from orgdatacore import (
    API_VERSION,
    __version__,
    __version_info__,
    check_api_compatibility,
    get_version_dict,
)


class TestVersion:
    """Tests for version information."""

    def test_version_is_string(self) -> None:
        """__version__ should be a string."""
        assert isinstance(__version__, str)

    def test_version_format(self) -> None:
        """__version__ should follow semver or PEP 440 format."""
        # Supports semver (1.0.0-dev.1) and PEP 440 (1.0.0.dev0) formats
        pattern = r"^\d+\.\d+\.\d+([-.]?[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$"
        assert re.match(pattern, __version__), f"Invalid version format: {__version__}"

    def test_version_info_is_tuple(self) -> None:
        """__version_info__ should be a tuple of 3 integers."""
        assert isinstance(__version_info__, tuple)
        assert len(__version_info__) == 3
        assert all(isinstance(x, int) for x in __version_info__)

    def test_version_info_matches_version(self) -> None:
        """__version_info__ should match __version__."""
        major, minor, patch = __version_info__
        assert __version__.startswith(f"{major}.{minor}.{patch}")

    def test_api_version_format(self) -> None:
        """API_VERSION should be a major.minor string."""
        pattern = r"^\d+\.\d+$"
        assert re.match(pattern, API_VERSION), f"Invalid API version: {API_VERSION}"


class TestAPICompatibility:
    """Tests for API compatibility checking."""

    def test_compatible_same_version(self) -> None:
        """Same version should be compatible."""
        assert check_api_compatibility(API_VERSION)

    def test_compatible_lower_minor(self) -> None:
        """Lower minor version should be compatible."""
        major = API_VERSION.split(".")[0]
        assert check_api_compatibility(f"{major}.0")

    def test_incompatible_different_major(self) -> None:
        """Different major version should be incompatible."""
        current_major = int(API_VERSION.split(".")[0])
        assert not check_api_compatibility(f"{current_major + 1}.0")
        if current_major > 0:
            assert not check_api_compatibility(f"{current_major - 1}.0")

    def test_incompatible_higher_minor(self) -> None:
        """Higher minor version should be incompatible."""
        major, minor = API_VERSION.split(".")
        assert not check_api_compatibility(f"{major}.{int(minor) + 1}")

    def test_invalid_version_string(self) -> None:
        """Invalid version strings should return False."""
        assert not check_api_compatibility("invalid")
        assert not check_api_compatibility("")
        assert not check_api_compatibility("a.b")
        # Note: "1" is valid as it's interpreted as "1.0"


class TestVersionDict:
    """Tests for get_version_dict."""

    def test_get_version_dict_keys(self) -> None:
        """get_version_dict should return expected keys."""
        d = get_version_dict()
        expected_keys = {
            "version",
            "version_info",
            "api_version",
            "major",
            "minor",
            "patch",
        }
        assert set(d.keys()) == expected_keys

    def test_get_version_dict_values(self) -> None:
        """get_version_dict should return consistent values."""
        d = get_version_dict()
        assert d["version"] == __version__
        assert d["version_info"] == __version_info__
        assert d["api_version"] == API_VERSION
        assert d["major"] == __version_info__[0]
        assert d["minor"] == __version_info__[1]
        assert d["patch"] == __version_info__[2]
