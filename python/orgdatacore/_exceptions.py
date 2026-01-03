"""Custom exceptions for orgdatacore.

This module defines a hierarchy of exceptions for better error handling:

    OrgDataError (base)
    ├── DataLoadError      - Failed to load/parse data
    ├── DataSourceError    - Data source operation failed
    │   ├── GCSError       - GCS-specific errors
    │   └── FileSourceError - File source errors (internal)
    └── ConfigurationError - Invalid configuration

Example:
    try:
        service.load_from_data_source(source)
    except DataLoadError as e:
        logger.error(f"Failed to load data: {e}")
    except DataSourceError as e:
        logger.error(f"Data source error: {e}")
"""


class OrgDataError(Exception):
    """Base exception for all orgdatacore errors."""

    pass


class DataLoadError(OrgDataError):
    """Failed to load or parse organizational data.

    Raised when:
    - JSON parsing fails
    - Data structure is invalid
    - Required fields are missing
    """

    pass


class DataSourceError(OrgDataError):
    """Data source operation failed.

    Base class for data source specific errors.
    """

    pass


class GCSError(DataSourceError):
    """Google Cloud Storage operation failed.

    Raised when:
    - GCS connection fails
    - Bucket/object not found
    - Authentication fails
    - Download fails
    """

    pass


class FileSourceError(DataSourceError):
    """File source operation failed (internal testing only).

    Raised when:
    - File not found
    - Permission denied
    - Read error
    """

    pass


class ConfigurationError(OrgDataError):
    """Invalid configuration provided.

    Raised when:
    - Required config fields are missing
    - Config values are invalid
    """

    pass
