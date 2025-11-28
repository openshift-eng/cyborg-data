"""
Data source implementations for orgdatacore.

This module provides the GCSDataSource for production use with Google Cloud Storage.

For custom data sources (e.g., S3, Azure Blob, etc.), implement the DataSource
interface from orgdatacore.interface.

Example custom implementation:

    from orgdatacore.interface import DataSource
    from typing import BinaryIO, Callable, Optional
    from io import BytesIO

    class S3DataSource(DataSource):
        def __init__(self, bucket: str, key: str):
            self.bucket = bucket
            self.key = key

        def load(self) -> BinaryIO:
            # Your S3 loading logic here
            import boto3
            s3 = boto3.client('s3')
            response = s3.get_object(Bucket=self.bucket, Key=self.key)
            return BytesIO(response['Body'].read())

        def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
            # Your S3 watching logic here (polling, S3 events, etc.)
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

from .interface import DataSource
from .types import GCSConfig


class GCSDataSource(DataSource):
    """
    GCSDataSource is a stub for GCS support.

    IMPORTANT: This is the ONLY supported production data source out of the box.
    File-based data sources have been removed from the public API for security reasons.
    All production deployments must use GCS with proper access controls, or implement
    a custom DataSource (e.g., S3, Azure Blob Storage).

    To enable actual GCS support, install the google-cloud-storage package
    and use GCSDataSourceWithSDK instead.

    For custom data sources, implement the DataSource interface:

        from orgdatacore.interface import DataSource

        class MyCustomDataSource(DataSource):
            def load(self) -> BinaryIO:
                ...
            def watch(self, callback) -> Optional[Exception]:
                ...
            def __str__(self) -> str:
                ...
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
            RuntimeError: Always, as this is a stub implementation.
        """
        raise RuntimeError(
            "GCS support not enabled: install google-cloud-storage and use "
            "GCSDataSourceWithSDK(). File-based data sources have been deprecated "
            "for security reasons. GCS is the only supported production data source. "
            "Alternatively, implement a custom DataSource for your storage backend."
        )

    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        """
        Returns an error indicating GCS support is not enabled.

        Returns:
            RuntimeError: Always, as this is a stub implementation.
        """
        return RuntimeError(
            "GCS support not enabled: install google-cloud-storage and use "
            "GCSDataSourceWithSDK()"
        )

    def __str__(self) -> str:
        """Return a description of this data source."""
        return (
            f"gs://{self.config.bucket}/{self.config.object_path} "
            "(stub - install google-cloud-storage for actual support)"
        )


# Optional: GCS implementation with actual SDK support
try:
    from google.cloud import storage  # type: ignore

    class GCSDataSourceWithSDK(DataSource):
        """
        GCSDataSourceWithSDK provides actual GCS support using the Google Cloud SDK.

        Requires the google-cloud-storage package to be installed:
            pip install google-cloud-storage

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

        def __init__(self, config: GCSConfig) -> None:
            """Create a GCS data source with SDK support."""
            self.config = config
            self._client: Optional[storage.Client] = None
            self._stop_event = threading.Event()

        def _get_client(self) -> storage.Client:
            """Get or create the GCS client."""
            if self._client is None:
                if self.config.credentials_json:
                    self._client = storage.Client.from_service_account_json(
                        self.config.credentials_json
                    )
                else:
                    self._client = storage.Client(project=self.config.project_id)
            return self._client

        def load(self) -> BinaryIO:
            """Load and return a reader for the organizational data from GCS."""
            client = self._get_client()
            bucket = client.bucket(self.config.bucket)
            blob = bucket.blob(self.config.object_path)

            content = blob.download_as_bytes()
            return BytesIO(content)

        def watch(
            self, callback: Callable[[], Optional[Exception]]
        ) -> Optional[Exception]:
            """
            Monitor for changes and call callback when data is updated.

            Uses polling based on the configured check interval.
            """
            client = self._get_client()
            bucket = client.bucket(self.config.bucket)
            blob = bucket.blob(self.config.object_path)

            # Get initial generation
            blob.reload()
            last_generation = blob.generation

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
                            last_generation = blob.generation
                            callback()
                    except Exception:
                        # Log but don't crash the watcher
                        pass

            thread = threading.Thread(target=watcher, daemon=True)
            thread.start()
            return None

        def stop_watching(self) -> None:
            """Stop the GCS watcher."""
            self._stop_event.set()

        def __str__(self) -> str:
            """Return a description of this data source."""
            return f"gs://{self.config.bucket}/{self.config.object_path}"

except ImportError:
    # google-cloud-storage not available
    pass
