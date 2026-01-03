"""Tests for the exception hierarchy."""

import pytest

from orgdatacore import (
    ConfigurationError,
    DataLoadError,
    DataSourceError,
    GCSError,
    OrgDataError,
)
from orgdatacore._exceptions import FileSourceError


class TestExceptionHierarchy:
    """Test the exception class hierarchy."""

    def test_data_load_error_is_org_data_error(self):
        """DataLoadError should be a subclass of OrgDataError."""
        assert issubclass(DataLoadError, OrgDataError)
        assert issubclass(DataLoadError, Exception)

    def test_data_source_error_is_org_data_error(self):
        """DataSourceError should be a subclass of OrgDataError."""
        assert issubclass(DataSourceError, OrgDataError)

    def test_gcs_error_is_data_source_error(self):
        """GCSError should be a subclass of DataSourceError."""
        assert issubclass(GCSError, DataSourceError)
        assert issubclass(GCSError, OrgDataError)

    def test_file_source_error_is_data_source_error(self):
        """FileSourceError should be a subclass of DataSourceError."""
        assert issubclass(FileSourceError, DataSourceError)
        assert issubclass(FileSourceError, OrgDataError)

    def test_configuration_error_is_org_data_error(self):
        """ConfigurationError should be a subclass of OrgDataError."""
        assert issubclass(ConfigurationError, OrgDataError)


class TestCatchingExceptions:
    """Test that exceptions can be caught correctly."""

    def test_catch_org_data_error(self):
        """All orgdatacore errors can be caught with OrgDataError."""
        with pytest.raises(OrgDataError):
            raise DataLoadError("test")

        with pytest.raises(OrgDataError):
            raise GCSError("test")

        with pytest.raises(OrgDataError):
            raise ConfigurationError("test")

    def test_catch_data_source_error(self):
        """Data source errors can be caught with DataSourceError."""
        with pytest.raises(DataSourceError):
            raise GCSError("test")

        with pytest.raises(DataSourceError):
            raise FileSourceError("test")

    def test_exception_messages(self):
        """Exceptions should preserve their messages."""
        e = DataLoadError("Failed to load data")
        assert str(e) == "Failed to load data"

        e = GCSError("Bucket not found")
        assert str(e) == "Bucket not found"
