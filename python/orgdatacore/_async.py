"""Async service and data source implementations for orgdatacore.

This module provides async-compatible versions of Service and GCS data source
for use with asyncio-based frameworks like FastAPI, aiohttp, etc.

Example:
    from orgdatacore import AsyncService, GCSConfig
    from orgdatacore._async import AsyncGCSDataSource

    async def main():
        config = GCSConfig(bucket="my-bucket", object_path="data.json")
        source = AsyncGCSDataSource(config)

        service = AsyncService()
        await service.load_from_data_source(source)
        employee = await service.get_employee_by_uid("jdoe")
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO

from ._exceptions import ConfigurationError, DataLoadError, GCSError
from ._log import get_logger
from ._service import _parse_data
from ._types import (
    Data,
    DataVersion,
    Employee,
    GCSConfig,
    MembershipInfo,
    MembershipType,
    Org,
    OrgInfo,
    OrgInfoType,
    Pillar,
    Team,
    TeamGroup,
)

__all__ = ["AsyncService", "AsyncGCSDataSource"]

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0


class AsyncService:
    """Async implementation of the organizational data service.

    Thread-safe and asyncio-compatible. All lookup methods are async
    to allow for non-blocking operation in async contexts.

    Example:
        service = AsyncService()
        await service.load_from_data_source(source)
        employee = await service.get_employee_by_uid("jdoe")
    """

    def __init__(self, *, data_source: Any | None = None) -> None:
        """Initialize a new async organizational data service.

        Args:
            data_source: Optional async data source to load from immediately.
        """
        self._lock = asyncio.Lock()
        self._data: Data | None = None
        self._version = DataVersion()
        self._init_source = data_source
        self._watcher_running = False
        self._watcher_task: asyncio.Task[None] | None = None
        self._watcher_source: Any | None = None

    async def initialize(self) -> None:
        """Initialize the service if a data source was provided.

        Call this after construction if you passed a data_source to __init__.
        """
        if self._init_source is not None:
            await self.load_from_data_source(self._init_source)

    async def load_from_data_source(self, source: Any) -> None:
        """Load organizational data from an async data source.

        Args:
            source: Async data source with an async load() method.

        Raises:
            DataLoadError: If loading or parsing fails.
        """
        logger = get_logger()
        logger.debug("Loading data from async source", extra={"source": str(source)})

        try:
            # Support both sync and async data sources
            if asyncio.iscoroutinefunction(source.load):
                reader = await source.load()
            else:
                reader = await asyncio.to_thread(source.load)
        except Exception as e:
            logger.error("Failed to load from async data source", extra={"source": str(source), "error": str(e)})
            raise DataLoadError(f"failed to load from data source {source}: {e}") from e

        try:
            content = reader.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            raw_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON", extra={"source": str(source), "error": str(e)})
            raise DataLoadError(f"failed to parse JSON from source {source}: {e}") from e
        finally:
            reader.close()

        try:
            org_data = _parse_data(raw_data)
        except Exception as e:
            logger.error("Failed to parse data structure", extra={"source": str(source), "error": str(e)})
            raise DataLoadError(f"failed to parse data structure from source {source}: {e}") from e

        async with self._lock:
            self._data = org_data
            self._version = DataVersion(
                load_time=datetime.now(),
                org_count=len(org_data.lookups.orgs),
                employee_count=len(org_data.lookups.employees),
            )

        logger.info(
            "Data loaded successfully (async)",
            extra={
                "source": str(source),
                "employee_count": self._version.employee_count,
                "org_count": self._version.org_count,
            },
        )

    async def start_data_source_watcher(self, source: Any) -> None:
        """Start watching an async data source for changes.

        This method returns immediately after starting the watcher in the background.
        Use stop_watcher() to stop the watcher.

        Args:
            source: Async data source to watch.

        Raises:
            DataLoadError: If initial load fails.
            RuntimeError: If watcher is already running.
        """
        logger = get_logger()

        if self._watcher_running:
            raise RuntimeError("Watcher is already running")

        # Perform initial load (before starting background watcher)
        await self.load_from_data_source(source)

        self._watcher_running = True
        self._watcher_source = source

        async def _run_watcher() -> None:
            """Background watcher coroutine."""
            try:
                async def callback() -> Exception | None:
                    try:
                        logger.info("Reloading data from async source", extra={"source": str(source)})
                        await self.load_from_data_source(source)
                        return None
                    except Exception as e:
                        logger.error("Failed to reload data", extra={"source": str(source), "error": str(e)})
                        return e

                if hasattr(source, "watch"):
                    logger.info("Starting async data source watcher", extra={"source": str(source)})
                    if asyncio.iscoroutinefunction(source.watch):
                        err = await source.watch(callback)
                    else:
                        # Sync watch - run in thread with async-safe callback
                        loop = asyncio.get_running_loop()

                        def sync_callback() -> Exception | None:
                            future = asyncio.run_coroutine_threadsafe(callback(), loop)
                            try:
                                return future.result(timeout=60)
                            except Exception as e:
                                return e

                        err = await asyncio.to_thread(source.watch, sync_callback)
                    if err:
                        logger.error("Watcher error", extra={"source": str(source), "error": str(err)})
            except asyncio.CancelledError:
                logger.info("Watcher cancelled", extra={"source": str(source)})
                raise
            finally:
                self._watcher_running = False
                self._watcher_task = None
                self._watcher_source = None

        # Start as background task
        self._watcher_task = asyncio.create_task(_run_watcher())

    async def stop_watcher(self) -> None:
        """Stop the data source watcher if running.

        For sync data sources running via asyncio.to_thread(), calls source.stop()
        if available to signal the watch loop to exit. This enables cooperative
        cancellation since Python threads cannot be forcibly interrupted.
        """
        # Signal sync sources to stop (best effort)
        if self._watcher_source is not None:
            if hasattr(self._watcher_source, "stop"):
                try:
                    self._watcher_source.stop()
                except Exception:
                    pass  # Best effort - don't fail stop_watcher if stop() fails

        # Cancel the asyncio task
        if self._watcher_task is not None:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            self._watcher_task = None

        self._watcher_running = False
        self._watcher_source = None

    def is_healthy(self) -> bool:
        """Check if the service has data loaded."""
        return self._data is not None

    def is_ready(self) -> bool:
        """Check if the service is ready to serve requests."""
        if self._data is None:
            return False
        return self._data.lookups is not None and self._data.indexes is not None

    # Async lookup methods

    async def get_employee_by_uid(self, uid: str) -> Employee | None:
        """Get an employee by their UID."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.employees.get(uid)

    async def get_employee_by_email(self, email: str) -> Employee | None:
        """Get an employee by their email address."""
        async with self._lock:
            if self._data is None:
                return None
            for emp in self._data.lookups.employees.values():
                if emp.email.lower() == email.lower():
                    return emp
            return None

    async def get_employee_by_slack_id(self, slack_id: str) -> Employee | None:
        """Get an employee by their Slack ID."""
        async with self._lock:
            if self._data is None:
                return None
            uid = self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(slack_id)
            if uid:
                return self._data.lookups.employees.get(uid)
            return None

    async def get_employee_by_github_id(self, github_id: str) -> Employee | None:
        """Get an employee by their GitHub ID."""
        async with self._lock:
            if self._data is None:
                return None
            uid = self._data.indexes.github_id_mappings.github_id_to_uid.get(github_id)
            if uid:
                return self._data.lookups.employees.get(uid)
            return None

    async def get_team_by_name(self, name: str) -> Team | None:
        """Get a team by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.teams.get(name)

    async def get_org_by_name(self, name: str) -> Org | None:
        """Get an organization by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.orgs.get(name)

    async def get_pillar_by_name(self, name: str) -> Pillar | None:
        """Get a pillar by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.pillars.get(name)

    async def get_team_group_by_name(self, name: str) -> TeamGroup | None:
        """Get a team group by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.team_groups.get(name)

    async def get_user_memberships(self, uid: str) -> tuple[MembershipInfo, ...]:
        """Get all memberships for a user."""
        async with self._lock:
            if self._data is None:
                return ()
            return self._data.indexes.membership.membership_index.get(uid, ())

    async def get_user_teams(self, uid: str) -> tuple[str, ...]:
        """Get team names for a user."""
        memberships = await self.get_user_memberships(uid)
        return tuple(m.name for m in memberships if m.type == MembershipType.TEAM)

    async def get_user_organizations(self, uid: str) -> tuple[OrgInfo, ...]:
        """Get organization info for a user."""
        async with self._lock:
            if self._data is None:
                return ()

            memberships = self._data.indexes.membership.membership_index.get(uid, ())
            result: list[OrgInfo] = []

            for m in memberships:
                if m.type == MembershipType.ORG:
                    result.append(OrgInfo(name=m.name, type=OrgInfoType.ORGANIZATION))
                elif m.type == MembershipType.TEAM:
                    result.append(OrgInfo(name=m.name, type=OrgInfoType.TEAM))
                    # Add ancestry
                    rel_info = self._data.indexes.membership.relationship_index.get("teams", {}).get(m.name)
                    if rel_info:
                        for org in rel_info.ancestry.orgs:
                            result.append(OrgInfo(name=org, type=OrgInfoType.ORGANIZATION))
                        for pillar in rel_info.ancestry.pillars:
                            result.append(OrgInfo(name=pillar, type=OrgInfoType.PILLAR))
                        for tg in rel_info.ancestry.team_groups:
                            result.append(OrgInfo(name=tg, type=OrgInfoType.TEAM_GROUP))

            return tuple(result)

    async def get_all_employees(self) -> tuple[Employee, ...]:
        """Get all employees."""
        async with self._lock:
            if self._data is None:
                return ()
            return tuple(self._data.lookups.employees.values())

    async def get_all_teams(self) -> tuple[Team, ...]:
        """Get all teams."""
        async with self._lock:
            if self._data is None:
                return ()
            return tuple(self._data.lookups.teams.values())

    async def get_all_orgs(self) -> tuple[Org, ...]:
        """Get all organizations."""
        async with self._lock:
            if self._data is None:
                return ()
            return tuple(self._data.lookups.orgs.values())

    async def get_all_pillars(self) -> tuple[Pillar, ...]:
        """Get all pillars."""
        async with self._lock:
            if self._data is None:
                return ()
            return tuple(self._data.lookups.pillars.values())

    async def get_all_team_groups(self) -> tuple[TeamGroup, ...]:
        """Get all team groups."""
        async with self._lock:
            if self._data is None:
                return ()
            return tuple(self._data.lookups.team_groups.values())

    async def get_team_members(self, team_name: str) -> tuple[Employee, ...]:
        """Get all members of a team."""
        async with self._lock:
            if self._data is None:
                return ()
            team = self._data.lookups.teams.get(team_name)
            if not team:
                return ()
            result = []
            for uid in team.group.resolved_people_uid_list:
                emp = self._data.lookups.employees.get(uid)
                if emp:
                    result.append(emp)
            return tuple(result)

    async def get_org_members(self, org_name: str) -> tuple[Employee, ...]:
        """Get all members of an organization."""
        async with self._lock:
            if self._data is None:
                return ()
            org = self._data.lookups.orgs.get(org_name)
            if not org:
                return ()
            result = []
            for uid in org.group.resolved_people_uid_list:
                emp = self._data.lookups.employees.get(uid)
                if emp:
                    result.append(emp)
            return tuple(result)

    def get_version(self) -> DataVersion:
        """Get the current data version (sync - no lock needed for read)."""
        return self._version


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
    last_error: Exception | None = None

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


try:
    from google.cloud import storage  # type: ignore[import-untyped]

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
            self._client: storage.Client | None = None

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
            self, callback: Callable[[], Awaitable[Exception | None]]
        ) -> Exception | None:
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
