"""Async data source implementations for orgdatacore.

This module provides async-compatible data sources for use with AsyncService.

Example:
    from orgdatacore.async_datasources import AsyncGCSDataSource
    from orgdatacore.async_service import AsyncService

    async def main():
        config = GCSConfig(bucket="my-bucket", object_path="data.json")
        source = AsyncGCSDataSource(config)
        
        service = AsyncService()
        await service.load_from_data_source(source)
"""

import asyncio
from io import BytesIO
from typing import BinaryIO, Callable, Optional, Awaitable

from .exceptions import GCSError, ConfigurationError
from .logging import get_logger
from .types import GCSConfig

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0


async def _async_retry_with_backoff(
    operation: Callable[[], Awaitable[BinaryIO]],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = DEFAULT_RETRY_BACKOFF,
    operation_name: str = "operation",
) -> BinaryIO:
    """Execute an async operation with exponential backoff retry."""
    logger = get_logger()
    delay = initial_delay
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return await operation()
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
                await asyncio.sleep(delay)
                delay *= backoff
            else:
                logger.error(
                    f"{operation_name} failed after all retries",
                    extra={"attempts": max_retries + 1, "error": str(e)},
                )

    raise GCSError(f"{operation_name} failed after {max_retries + 1} attempts: {last_error}")


# Optional: Async GCS implementation
try:
    from google.cloud import storage

    class AsyncGCSDataSource:
        """Async GCS data source using google-cloud-storage.

        Wraps sync GCS operations in asyncio.to_thread for non-blocking I/O.

        Example:
            config = GCSConfig(
                bucket="my-bucket",
                object_path="data.json",
                project_id="my-project",
            )
            source = AsyncGCSDataSource(config)
            
            async with aiohttp.ClientSession():
                service = AsyncService()
                await service.load_from_data_source(source)
        """

        def __init__(
            self,
            config: GCSConfig,
            *,
            max_retries: int = DEFAULT_MAX_RETRIES,
            retry_delay: float = DEFAULT_RETRY_DELAY,
            retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        ) -> None:
            """Create an async GCS data source.

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

        def _get_client(self) -> storage.Client:
            """Get or create the GCS client (sync)."""
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

        async def load(self) -> BinaryIO:
            """Load data from GCS asynchronously.

            Returns:
                File-like object containing the JSON data.

            Raises:
                GCSError: If loading fails after all retries.
            """
            logger = get_logger()
            logger.debug(
                "Loading from GCS (async)",
                extra={"bucket": self.config.bucket, "object": self.config.object_path},
            )

            async def _download() -> BinaryIO:
                def _sync_download() -> BinaryIO:
                    client = self._get_client()
                    bucket = client.bucket(self.config.bucket)
                    blob = bucket.blob(self.config.object_path)
                    return BytesIO(blob.download_as_bytes())

                return await asyncio.to_thread(_sync_download)

            return await _async_retry_with_backoff(
                _download,
                max_retries=self.max_retries,
                initial_delay=self.retry_delay,
                backoff=self.retry_backoff,
                operation_name=f"GCS download gs://{self.config.bucket}/{self.config.object_path}",
            )

        async def watch(
            self, callback: Callable[[], Awaitable[Optional[Exception]]]
        ) -> Optional[Exception]:
            """Monitor for changes and call async callback when data is updated.

            Args:
                callback: Async function to call when data changes.

            Returns:
                Exception if watcher setup fails, None otherwise.
            """
            logger = get_logger()

            try:
                client = self._get_client()
                bucket = client.bucket(self.config.bucket)
                blob = bucket.blob(self.config.object_path)

                # Get initial generation (sync, but quick)
                await asyncio.to_thread(blob.reload)
                last_generation = blob.generation

                logger.info(
                    "Starting async GCS watcher",
                    extra={
                        "bucket": self.config.bucket,
                        "object": self.config.object_path,
                        "check_interval": str(self.config.check_interval),
                    },
                )
            except Exception as e:
                logger.error("Failed to initialize async GCS watcher", extra={"error": str(e)})
                return GCSError(f"Failed to initialize GCS watcher: {e}")

            async def watcher() -> None:
                nonlocal last_generation
                interval = self.config.check_interval.total_seconds()

                while True:
                    await asyncio.sleep(interval)

                    try:
                        await asyncio.to_thread(blob.reload)
                        if blob.generation != last_generation:
                            logger.info(
                                "GCS object changed, triggering async reload",
                                extra={
                                    "old_generation": last_generation,
                                    "new_generation": blob.generation,
                                },
                            )
                            last_generation = blob.generation
                            err = await callback()
                            if err:
                                logger.error("Async reload callback failed", extra={"error": str(err)})
                    except asyncio.CancelledError:
                        logger.info("Async GCS watcher cancelled")
                        break
                    except Exception as e:
                        logger.error("Async GCS watcher check failed", extra={"error": str(e)})

            # Start watcher as background task
            asyncio.create_task(watcher())
            return None

        def __str__(self) -> str:
            """Return a description of this data source."""
            return f"gs://{self.config.bucket}/{self.config.object_path} (async)"

except ImportError:
    # google-cloud-storage not available
    pass

