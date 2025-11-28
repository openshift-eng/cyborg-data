"""Pytest configuration and fixtures for orgdatacore tests."""

from pathlib import Path

import pytest

from orgdatacore import Service

# Import from internal testing module - NOT part of public API
from orgdatacore.internal.testing import FileDataSource


@pytest.fixture
def test_data_path() -> Path:
    """Get path to the test data file."""
    # Go up from python/tests to the root, then into testdata
    return Path(__file__).parent.parent.parent / "testdata" / "test_org_data.json"


@pytest.fixture
def service(test_data_path: Path) -> Service:
    """Create a service loaded with test data."""
    svc = Service()
    file_source = FileDataSource(str(test_data_path))
    svc.load_from_data_source(file_source)
    return svc


@pytest.fixture
def empty_service() -> Service:
    """Create an empty service with no data loaded."""
    return Service()
