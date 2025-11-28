"""
Data source implementations for orgdatacore.

This module provides the GCSDataSource for production use with Google Cloud Storage.

For custom data sources (e.g., S3, Azure Blob, etc.), implement the DataSource
protocol from orgdatacore.interface.

Example custom implementation:

    from typing import BinaryIO, Callable, Optional
    from io import BytesIO

    class S3DataSource:  # No inheritance needed - just implement the methods
        def __init__(self, bucket: str, key: str):
            self.bucket = bucket
            self.key = key

        def load(self) -> BinaryIO:
            import boto3
            s3 = boto3.client('s3')
            response = s3.get_object(Bucket=self.bucket, Key=self.key)
            return BytesIO(response['Body'].read())

        def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
            # Your S3 watching logic here
            return None

        def __str__(self) -> str:
            return f"s3://{self.bucket}/{self.key}"

IMPORTANT: File-based data sources have been removed from the public API for
security reasons. All production deployments should use GCS or a custom
DataSource implementation with proper access controls.
"""

import threading
import time
from io import BytesIO
from typing import BinaryIO, Callable, Optional

from .exceptions import GCSError, ConfigurationError
from .logging import get_logger
from .types import GCSConfig

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_RETRY_BACKOFF = 2.0  # multiplier


class GCSDataSource:
    """
    GCSDataSource is a stub for GCS support.

    IMPORTANT: This is the ONLY supported production data source out of the box.
    File-based data sources have been removed from the public API for security reasons.
    All production deployments must use GCS with proper access controls, or implement
    a custom DataSource (e.g., S3, Azure Blob Storage).

    To enable actual GCS support, install the google-cloud-storage package
    and use GCSDataSourceWithSDK instead.

    For custom data sources, implement the DataSource protocol:

        class MyCustomDataSource:
            def load(self) -> BinaryIO: ...
            def watch(self, callback) -> Optional[Exception]: ...
            def __str__(self) -> str: ...
    """

    def __init__(self, config: GCSConfig) -> None:
        """
        Create a stub GCS data source.

        For production use with actual GCS functionality, install google-cloud-storage
        and use GCSDataSourceWithSDK instead.

        Args:
            config: GCS configuration with bucket, object path, etc.
        """
        self.config = config

    def load(self) -> BinaryIO:
        """
        Returns an error indicating GCS support is not enabled.

        Raises:
            GCSError: Always, as this is a stub implementation.
        """
        raise GCSError(
            "GCS support not enabled: install google-cloud-storage and use "
            "GCSDataSourceWithSDK(). File-based data sources have been deprecated "
            "for security reasons. GCS is the only supported production data source. "
            "Alternatively, implement a custom DataSource for your storage backend."
        )

    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        """
        Returns an error indicating GCS support is not enabled.

        Returns:
            GCSError: Always, as this is a stub implementation.
        """
        return GCSError(
            "GCS support not enabled: install google-cloud-storage and use "
            "GCSDataSourceWithSDK()"
        )

    def __str__(self) -> str:
        """Return a description of this data source."""
        return (
            f"gs://{self.config.bucket}/{self.config.object_path} "
            "(stub - install google-cloud-storage for actual support)"
        )


def _retry_with_backoff(
    operation: Callable[[], BinaryIO],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = DEFAULT_RETRY_BACKOFF,
    operation_name: str = "operation",
) -> BinaryIO:
    """Execute an operation with exponential backoff retry.

    Args:
        operation: Callable to execute.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each retry.
        operation_name: Name of operation for logging.

    Returns:
        Result of the operation.

    Raises:
        GCSError: If all retries are exhausted.
    """
    logger = get_logger()
    delay = initial_delay
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"{operation_name} failed, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "delay": delay,
                        "error": str(e),
                    },
                )
                time.sleep(delay)
                delay *= backoff
            else:
                logger.error(
                    f"{operation_name} failed after all retries",
                    extra={
                        "attempts": max_retries + 1,
                        "error": str(e),
                    },
                )

    raise GCSError(f"{operation_name} failed after {max_retries + 1} attempts: {last_error}")


# Optional: GCS implementation with actual SDK support
try:
    from google.cloud import storage

    class GCSDataSourceWithSDK:
        """
        GCSDataSourceWithSDK provides actual GCS support using the Google Cloud SDK.

        Requires the google-cloud-storage package to be installed:
            pip install google-cloud-storage

        Features:
        - Automatic retry with exponential backoff for transient failures
        - Structured logging for observability
        - Proper error handling with custom exceptions

        Example:
            from orgdatacore import GCSConfig
            from orgdatacore.datasources import GCSDataSourceWithSDK
            from datetime import timedelta

            config = GCSConfig(
                bucket="your-bucket",
                object_path="path/to/data.json",
                project_id="your-project",
                check_interval=timedelta(minutes=5),
            )
            source = GCSDataSourceWithSDK(config)
            service.load_from_data_source(source)
        """

        def __init__(
            self,
            config: GCSConfig,
            *,
            max_retries: int = DEFAULT_MAX_RETRIES,
            retry_delay: float = DEFAULT_RETRY_DELAY,
            retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        ) -> None:
            """Create a GCS data source with SDK support.

            Args:
                config: GCS configuration.
                max_retries: Maximum retry attempts for transient failures.
                retry_delay: Initial delay between retries in seconds.
                retry_backoff: Multiplier for delay after each retry.

            Raises:
                ConfigurationError: If configuration is invalid.
            """
            if not config.bucket:
                raise ConfigurationError("GCS bucket is required")
            if not config.object_path:
                raise ConfigurationError("GCS object_path is required")

            self.config = config
            self.max_retries = max_retries
            self.retry_delay = retry_delay
            self.retry_backoff = retry_backoff
            self._client: Optional[storage.Client] = None
            self._stop_event = threading.Event()

        def _get_client(self) -> storage.Client:
            """Get or create the GCS client."""
            if self._client is None:
                logger = get_logger()
                logger.debug("Creating GCS client", extra={"project_id": self.config.project_id})

                if self.config.credentials_json:
                    self._client = storage.Client.from_service_account_json(
                        self.config.credentials_json
                    )
                else:
                    self._client = storage.Client(project=self.config.project_id or None)
            return self._client

        def load(self) -> BinaryIO:
            """Load and return a reader for the organizational data from GCS.

            Returns:
                File-like object containing the JSON data.

            Raises:
                GCSError: If loading fails after all retries.
            """
            logger = get_logger()
            logger.debug(
                "Loading from GCS",
                extra={"bucket": self.config.bucket, "object": self.config.object_path},
            )

            def _download() -> BinaryIO:
                client = self._get_client()
                bucket = client.bucket(self.config.bucket)
                blob = bucket.blob(self.config.object_path)
                content = blob.download_as_bytes()
                return BytesIO(content)

            return _retry_with_backoff(
                _download,
                max_retries=self.max_retries,
                initial_delay=self.retry_delay,
                backoff=self.retry_backoff,
                operation_name=f"GCS download gs://{self.config.bucket}/{self.config.object_path}",
            )

        def watch(
            self, callback: Callable[[], Optional[Exception]]
        ) -> Optional[Exception]:
            """
            Monitor for changes and call callback when data is updated.

            Uses polling based on the configured check interval.
            Detects changes by comparing object generation numbers.

            Args:
                callback: Function to call when data changes.

            Returns:
                Exception if watcher setup fails, None otherwise.
            """
            logger = get_logger()

            try:
                client = self._get_client()
                bucket = client.bucket(self.config.bucket)
                blob = bucket.blob(self.config.object_path)

                # Get initial generation
                blob.reload()
                last_generation = blob.generation

                logger.info(
                    "Starting GCS watcher",
                    extra={
                        "bucket": self.config.bucket,
                        "object": self.config.object_path,
                        "check_interval": str(self.config.check_interval),
                        "initial_generation": last_generation,
                    },
                )
            except Exception as e:
                logger.error("Failed to initialize GCS watcher", extra={"error": str(e)})
                return GCSError(f"Failed to initialize GCS watcher: {e}")

            def watcher() -> None:
                nonlocal last_generation
                interval = self.config.check_interval.total_seconds()

                while not self._stop_event.is_set():
                    time.sleep(interval)
                    if self._stop_event.is_set():
                        break

                    try:
                        blob.reload()
                        if blob.generation != last_generation:
                            logger.info(
                                "GCS object changed, triggering reload",
                                extra={
                                    "old_generation": last_generation,
                                    "new_generation": blob.generation,
                                },
                            )
                            last_generation = blob.generation
                            err = callback()
                            if err:
                                logger.error("Reload callback failed", extra={"error": str(err)})
                    except Exception as e:
                        logger.error("GCS watcher check failed", extra={"error": str(e)})

            thread = threading.Thread(target=watcher, daemon=True, name="gcs-watcher")
            thread.start()
            return None

        def stop_watching(self) -> None:
            """Stop the GCS watcher."""
            logger = get_logger()
            logger.info("Stopping GCS watcher")
            self._stop_event.set()

        def __str__(self) -> str:
            """Return a description of this data source."""
            return f"gs://{self.config.bucket}/{self.config.object_path}"

except ImportError:
    # google-cloud-storage not available
    pass
