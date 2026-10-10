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
import inspect
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any, BinaryIO, TypeVar

from ._exceptions import (
    ConfigurationError,
    DataLoadError,
    GCSError,
    TimeTravelNotSupportedError,
    VersionNotAvailableError,
)
from ._log import get_logger
from ._service import (
    DEFAULT_HISTORY_CACHE_SIZE,
    DEFAULT_VERSIONS_CACHE_TTL,
    _ancestor_org_info_type,
    _EntityRef,
    _NameTypeKey,
    _normalize_slack_channel,
    _resolve_version,
    _to_entity_type,
    parse_data,
)
from ._types import (
    Component,
    ComponentOwnerInfo,
    ComponentOwnership,
    ContextItemInfo,
    Data,
    DataVersion,
    DataVersionRef,
    Employee,
    EntityType,
    EscalationContactInfo,
    GCSConfig,
    HierarchyNode,
    HierarchyPathEntry,
    HistoricalDataSource,
    JiraOwnerInfo,
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

_T = TypeVar("_T")


class AsyncService:
    """Async implementation of the organizational data service.

    Thread-safe and asyncio-compatible. All lookup methods are async
    to allow for non-blocking operation in async contexts.

    Example:
        service = AsyncService()
        await service.load_from_data_source(source)
        employee = await service.get_employee_by_uid("jdoe")
    """

    def __init__(
        self,
        *,
        data_source: Any | None = None,
        history_cache_size: int = DEFAULT_HISTORY_CACHE_SIZE,
        versions_cache_ttl: float = DEFAULT_VERSIONS_CACHE_TTL,
    ) -> None:
        """Initialize a new async organizational data service.

        Args:
            data_source: Optional async data source to load from immediately.
            history_cache_size: Number of historical snapshots as_of keeps cached
                in memory (LRU). A size <= 0 disables caching.
            versions_cache_ttl: Seconds as_of/list_versions reuse a cached version
                listing before re-querying the source. <= 0 disables it.
        """
        self._lock = asyncio.Lock()
        self._data: Data | None = None
        self._version = DataVersion()
        self._init_source = data_source
        self._watcher_running = False
        self._watcher_task: asyncio.Task[None] | None = None
        self._watcher_source: Any | None = None
        self._slack_channel_index: dict[str, list[str]] = {}

        # Historical snapshot cache for as_of, keyed by "source@version_id" (LRU),
        # so snapshots from a raw source and a wrapper over it never collide.
        self._history_cache: OrderedDict[str, AsyncService] = OrderedDict()
        self._history_cache_size = history_cache_size

        # Short-TTL cache of version listings, keyed by source string.
        self._versions_cache: dict[str, tuple[float, list[DataVersionRef]]] = {}
        self._versions_ttl = versions_cache_ttl

        # Derived identity indexes, rebuilt on every load. Populated only when
        # the index carries stable IDs (_use_stable_ids); otherwise traversal
        # falls back to the legacy name+type behavior.
        self._entity_by_id: dict[str, _EntityRef] = {}
        self._children_by_id: dict[str, list[str]] = {}
        self._id_by_name_type: dict[_NameTypeKey, str] = {}
        self._use_stable_ids: bool = False

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
            if inspect.iscoroutinefunction(source.load):
                reader = await source.load()
            else:
                reader = await asyncio.to_thread(source.load)
        except Exception as e:
            logger.error(
                "Failed to load from async data source",
                extra={"source": str(source), "error": str(e)},
            )
            raise DataLoadError(f"failed to load from data source {source}: {e}") from e

        await self._apply_reader(reader, str(source))

    async def _apply_reader(self, reader: BinaryIO, source_desc: str) -> None:
        """Decode, parse, and swap in index JSON read from ``reader``.

        Shared core of ``load_from_data_source`` and ``as_of``. ``source_desc`` is
        used only for error messages and logging. The reader is closed here.
        """
        logger = get_logger()

        try:
            raw_content = reader.read()
            text = (
                raw_content.decode("utf-8")
                if isinstance(raw_content, bytes)
                else raw_content
            )
            raw_data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON", extra={"source": source_desc, "error": str(e)}
            )
            raise DataLoadError(
                f"failed to parse JSON from source {source_desc}: {e}"
            ) from e
        finally:
            reader.close()

        try:
            org_data = parse_data(raw_data)
        except Exception as e:
            logger.error(
                "Failed to parse data structure",
                extra={"source": source_desc, "error": str(e)},
            )
            raise DataLoadError(
                f"failed to parse data structure from source {source_desc}: {e}"
            ) from e

        async with self._lock:
            self._data = org_data
            self._version = DataVersion(
                load_time=datetime.now(),
                org_count=len(org_data.lookups.orgs),
                employee_count=len(org_data.lookups.employees),
            )

            self._slack_channel_index = {}
            for team in org_data.lookups.teams.values():
                if team.group.slack is None:
                    continue
                for ch in team.group.slack.channels:
                    if ch.channel:
                        normalized = _normalize_slack_channel(ch.channel)
                        self._slack_channel_index.setdefault(normalized, []).append(team.name)

            self._build_derived_indexes()

        logger.info(
            "Data loaded successfully (async)",
            extra={
                "source": source_desc,
                "employee_count": self._version.employee_count,
                "org_count": self._version.org_count,
            },
        )

    async def list_versions(self, source: Any) -> list[DataVersionRef]:
        """List all retained versions of the index, sorted oldest-first.

        Raises:
            TimeTravelNotSupportedError: If source does not retain history.
            DataLoadError: If listing fails.
        """
        if not isinstance(source, HistoricalDataSource):
            raise TimeTravelNotSupportedError(
                f"data source does not support time travel: {source}"
            )
        return list(await self._list_versions_cached(source))

    async def as_of(self, source: Any, t: datetime) -> "AsyncService":
        """Return a read-only AsyncService bound to the version live at time ``t``.

        See Service.as_of for resolution semantics. Supports both sync and async
        historical sources.

        Raises:
            TimeTravelNotSupportedError: If source does not retain history.
            VersionNotAvailableError: If ``t`` predates the oldest retained version.
            DataLoadError: If loading the resolved version fails.
        """
        if not isinstance(source, HistoricalDataSource):
            raise TimeTravelNotSupportedError(
                f"data source does not support time travel: {source}"
            )

        refs = await self._list_versions_cached(source)
        ref = _resolve_version(refs, t)

        # Key the snapshot cache by source *and* version so a snapshot resolved
        # through, e.g., a redacting wrapper is never served to a raw source.
        cache_key = f"{source}@{ref.id}"
        cached = self._get_cached_view(cache_key)
        if cached is not None:
            return cached

        if inspect.iscoroutinefunction(source.load_version):
            reader = await source.load_version(ref)
        else:
            reader = await asyncio.to_thread(source.load_version, ref)

        view = AsyncService()
        await view._apply_reader(reader, cache_key)
        self._put_cached_view(cache_key, view)
        return view

    async def _list_versions_cached(self, source: Any) -> list[DataVersionRef]:
        """Return the sorted version listing for source, reusing a cached listing
        within versions_cache_ttl. Returned list is the cached one (read-only).
        """
        key = str(source)
        if self._versions_ttl > 0:
            entry = self._versions_cache.get(key)
            if entry is not None and (time.monotonic() - entry[0]) < self._versions_ttl:
                return entry[1]
        refs = await self._call_list_versions(source)
        refs = sorted(refs, key=lambda r: r.created)
        if self._versions_ttl > 0:
            self._versions_cache[key] = (time.monotonic(), refs)
        return refs

    async def _call_list_versions(self, source: Any) -> list[DataVersionRef]:
        try:
            if inspect.iscoroutinefunction(source.list_versions):
                refs: list[DataVersionRef] = await source.list_versions()
            else:
                refs = await asyncio.to_thread(source.list_versions)
        except TimeTravelNotSupportedError:
            raise
        except Exception as e:
            raise DataLoadError(f"failed to list versions from {source}: {e}") from e
        return refs

    def _get_cached_view(self, key: str) -> "AsyncService | None":
        if self._history_cache_size <= 0:
            return None
        view = self._history_cache.get(key)
        if view is not None:
            self._history_cache.move_to_end(key)
        return view

    def _put_cached_view(self, key: str, view: "AsyncService") -> None:
        if self._history_cache_size <= 0:
            return
        self._history_cache[key] = view
        self._history_cache.move_to_end(key)
        while len(self._history_cache) > self._history_cache_size:
            self._history_cache.popitem(last=False)

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
                        logger.info(
                            "Reloading data from async source",
                            extra={"source": str(source)},
                        )
                        await self.load_from_data_source(source)
                        return None
                    except Exception as e:
                        logger.error(
                            "Failed to reload data",
                            extra={"source": str(source), "error": str(e)},
                        )
                        return e

                if hasattr(source, "watch"):
                    logger.info(
                        "Starting async data source watcher",
                        extra={"source": str(source)},
                    )
                    if inspect.iscoroutinefunction(source.watch):
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
                        logger.error(
                            "Watcher error",
                            extra={"source": str(source), "error": str(err)},
                        )
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
        return bool(self._data.lookups.employees) or self._data.metadata.pii_free

    def get_data_age(self) -> timedelta:
        """Get the duration since data was last loaded.

        Returns:
            timedelta since last load, or timedelta(0) if no data loaded.
        """
        if self._version.load_time == datetime.min:
            return timedelta(0)
        return datetime.now() - self._version.load_time

    def is_data_stale(self, max_age: timedelta) -> bool:
        """Check if data is older than max_age, or if no data is loaded.

        Use this in health checks to detect stale data from failed reloads.

        Args:
            max_age: Maximum acceptable age for the data.

        Returns:
            True if data is stale or not loaded, False otherwise.
        """
        if self._data is None or self._version.load_time == datetime.min:
            return True
        return (datetime.now() - self._version.load_time) > max_age

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

    async def get_team_by_name(self, team_name: str) -> Team | None:
        """Get a team by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.teams.get(team_name)

    async def get_teams_by_slack_channel(self, channel: str) -> list[Team]:
        """Get teams associated with a Slack channel name.

        Args:
            channel: Slack channel name (e.g., "#test-team" or "test-team").
                     The "#" prefix and casing are ignored.

        Returns:
            List of matching teams, or empty list if none found.
        """
        async with self._lock:
            if self._data is None or not channel:
                return []

            team_names = self._slack_channel_index.get(
                _normalize_slack_channel(channel), []
            )
            return [
                self._data.lookups.teams[name]
                for name in team_names
                if name in self._data.lookups.teams
            ]

    async def get_team_escalation(self, team_name: str) -> list[EscalationContactInfo]:
        """Get the escalation contacts for a team.

        Args:
            team_name: The team name to look up.

        Returns:
            Ordered list of escalation contacts, or empty list if team
            not found or has no escalation data.
        """
        async with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []
            team = self._data.lookups.teams.get(team_name)
            if team is None:
                return []
            return list(team.group.escalation)

    async def get_org_by_name(self, org_name: str) -> Org | None:
        """Get an organization by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.orgs.get(org_name)

    async def get_pillar_by_name(self, pillar_name: str) -> Pillar | None:
        """Get a pillar by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.pillars.get(pillar_name)

    async def get_team_group_by_name(self, team_group_name: str) -> TeamGroup | None:
        """Get a team group by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.team_groups.get(team_group_name)

    async def get_component_by_name(self, component_name: str) -> Component | None:
        """Get a component by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.components.get(component_name)

    async def get_user_memberships(self, uid: str) -> list[MembershipInfo]:
        """Get all memberships for a user."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.indexes.membership.membership_index.get(uid, ()))

    async def get_user_teams(self, uid: str) -> list[str]:
        """Get team names for a user."""
        memberships = await self.get_user_memberships(uid)
        return [m.name for m in memberships if m.type == MembershipType.TEAM]

    async def get_teams_for_uid(self, uid: str) -> list[str]:
        """Get all teams a UID is a member of."""
        return await self.get_user_teams(uid)

    async def get_teams_for_slack_id(self, slack_id: str) -> list[str]:
        """Get all teams a Slack user is a member of."""
        uid = await self._get_uid_from_slack_id(slack_id)
        if not uid:
            return []
        return await self.get_teams_for_uid(uid)

    async def _get_uid_from_slack_id(self, slack_id: str) -> str:
        """Get the UID for a given Slack ID."""
        async with self._lock:
            if self._data is None:
                return ""
            return self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(
                slack_id, ""
            )

    async def get_manager_for_employee(self, uid: str) -> Employee | None:
        """Get the manager for a given employee UID."""
        async with self._lock:
            if self._data is None:
                return None
            emp = self._data.lookups.employees.get(uid)
            if not emp or not emp.manager_uid:
                return None
            return self._data.lookups.employees.get(emp.manager_uid)

    async def is_employee_in_team(self, uid: str, team_name: str) -> bool:
        """Check if an employee is in a specific team."""
        teams = await self.get_teams_for_uid(uid)
        return team_name in teams

    async def is_slack_user_in_team(self, slack_id: str, team_name: str) -> bool:
        """Check if a Slack user is in a specific team."""
        uid = await self._get_uid_from_slack_id(slack_id)
        if not uid:
            return False
        return await self.is_employee_in_team(uid, team_name)

    async def is_employee_in_org(self, uid: str, org_name: str) -> bool:
        """Check if an employee is in a specific organization."""
        async with self._lock:
            if self._data is None:
                return False

            memberships = self._data.indexes.membership.membership_index.get(uid, ())

            for membership in memberships:
                if (
                    membership.type == MembershipType.ORG
                    and membership.name == org_name
                ):
                    return True
                elif membership.type == MembershipType.TEAM:
                    hierarchy_path = self._get_hierarchy_path(
                        membership.name, EntityType.TEAM
                    )
                    for entry in hierarchy_path:
                        if entry.type == EntityType.ORG and entry.name == org_name:
                            return True

            return False

    async def is_slack_user_in_org(self, slack_id: str, org_name: str) -> bool:
        """Check if a Slack user is in a specific organization."""
        uid = await self._get_uid_from_slack_id(slack_id)
        if not uid:
            return False
        return await self.is_employee_in_org(uid, org_name)

    def _build_derived_indexes(self) -> None:
        """Build stable-ID relationship indexes from the loaded data.

        Caller must hold the lock. Enables ``_use_stable_ids`` only when the
        index is a sound identity graph: every entity carries a unique
        ``stable_id``, every parent edge carries a ``parent_id``, and every
        ``parent_id`` resolves to a known entity. Any defect (or an old-format
        index) falls back to the legacy name+type traversal rather than silently
        returning wrong ancestry.
        """
        self._entity_by_id = {}
        self._children_by_id = {}
        self._id_by_name_type = {}
        self._use_stable_ids = False
        if self._data is None:
            return

        any_stable_id = True
        all_edges_identified = True
        duplicate_stable_id = False

        def register(
            name: str,
            typ: EntityType,
            stable_id: str,
            parent_id: str,
            has_parent: bool,
        ) -> None:
            nonlocal any_stable_id, all_edges_identified, duplicate_stable_id
            if not stable_id:
                any_stable_id = False
                return
            if stable_id in self._entity_by_id:
                duplicate_stable_id = True
            self._entity_by_id[stable_id] = _EntityRef(
                name=name, type=typ, parent_id=parent_id, stable_id=stable_id
            )
            self._id_by_name_type[_NameTypeKey(name, typ)] = stable_id
            if has_parent and not parent_id:
                all_edges_identified = False

        for name, team in self._data.lookups.teams.items():
            register(name, EntityType.TEAM, team.stable_id, team.parent_id, team.parent is not None)
        for name, org in self._data.lookups.orgs.items():
            register(name, EntityType.ORG, org.stable_id, org.parent_id, org.parent is not None)
        for name, pillar in self._data.lookups.pillars.items():
            register(
                name, EntityType.PILLAR, pillar.stable_id, pillar.parent_id, pillar.parent is not None
            )
        for name, tg in self._data.lookups.team_groups.items():
            register(
                name, EntityType.TEAM_GROUP, tg.stable_id, tg.parent_id, tg.parent is not None
            )

        # Every parent_id must resolve to a known entity, otherwise traversal
        # would silently truncate ancestry or drop a descendants branch.
        all_parents_resolve = all(
            ref.parent_id in self._entity_by_id
            for ref in self._entity_by_id.values()
            if ref.parent_id
        )

        if (
            not self._entity_by_id
            or not any_stable_id
            or not all_edges_identified
            or duplicate_stable_id
            or not all_parents_resolve
        ):
            self._entity_by_id = {}
            self._id_by_name_type = {}
            return

        for stable_id, ref in self._entity_by_id.items():
            if ref.parent_id:
                self._children_by_id.setdefault(ref.parent_id, []).append(stable_id)

        self._use_stable_ids = True

    def _get_entity_type(self, entity_name: str) -> str:
        """Look up entity type by scanning lookups (first match)."""
        if self._data is None:
            return ""
        if entity_name in self._data.lookups.teams:
            return "team"
        if entity_name in self._data.lookups.orgs:
            return "org"
        if entity_name in self._data.lookups.pillars:
            return "pillar"
        if entity_name in self._data.lookups.team_groups:
            return "team_group"
        return ""

    def _resolve_start_id(self, entity_name: str, entity_type: str) -> str:
        """Map a (name, type) pair to a stable ID. Caller must hold the lock."""
        if not entity_type:
            inferred = self._get_entity_type(entity_name)
            if not inferred:
                return ""
            entity_type = inferred
        etype = _to_entity_type(entity_type.lower())
        if etype is None:
            return ""
        return self._id_by_name_type.get(_NameTypeKey(entity_name, etype), "")

    def _get_entity_by_type(
        self, entity_name: str, entity_type: str
    ) -> Team | Org | Pillar | TeamGroup | None:
        """Get entity from lookups by name and type."""
        if self._data is None:
            return None
        entity_type_lower = entity_type.lower()
        if entity_type_lower == "team":
            return self._data.lookups.teams.get(entity_name)
        elif entity_type_lower == "org":
            return self._data.lookups.orgs.get(entity_name)
        elif entity_type_lower == "pillar":
            return self._data.lookups.pillars.get(entity_name)
        elif entity_type_lower == "team_group":
            return self._data.lookups.team_groups.get(entity_name)
        return None

    def _get_hierarchy_path(
        self, entity_name: str, entity_type: str
    ) -> list[HierarchyPathEntry]:
        """Compute hierarchy path by walking parent references."""
        if self._data is None:
            return []

        if self._use_stable_ids:
            return self._compute_hierarchy_path_by_id(entity_name, entity_type)

        entity = self._get_entity_by_type(entity_name, entity_type)
        if entity is None:
            return []

        path = [HierarchyPathEntry(name=entity_name, type=entity_type)]
        visited = {entity_name}
        current: Team | Org | Pillar | TeamGroup | None = entity

        while current and current.parent:
            parent = current.parent
            if parent.name in visited:
                break
            visited.add(parent.name)
            path.append(HierarchyPathEntry(name=parent.name, type=parent.type))
            current = self._get_entity_by_type(parent.name, parent.type)

        return path

    def _compute_hierarchy_path_by_id(
        self, entity_name: str, entity_type: str
    ) -> list[HierarchyPathEntry]:
        """Walk the parent chain by stable ID. Caller must hold the lock."""
        start_id = self._resolve_start_id(entity_name, entity_type)
        if not start_id:
            return []

        path: list[HierarchyPathEntry] = []
        visited: set[str] = set()
        current_id = start_id
        while current_id and current_id not in visited:
            visited.add(current_id)
            ref = self._entity_by_id.get(current_id)
            if ref is None:
                break
            path.append(
                HierarchyPathEntry(
                    name=ref.name, type=ref.type, stable_id=ref.stable_id
                )
            )
            current_id = ref.parent_id
        return path

    async def get_hierarchy_path(
        self, entity_name: str, entity_type: str = "team"
    ) -> list[HierarchyPathEntry]:
        """Get ordered hierarchy path from entity to root.

        Computes path by walking parent references in entities.

        Args:
            entity_name: Name of the team/org/pillar/team_group
            entity_type: Type of entity ("team", "org", "pillar", "team_group")

        Returns:
            Ordered list from entity to root. Empty list if not found.
        """
        async with self._lock:
            return self._get_hierarchy_path(entity_name, entity_type)

    async def get_descendants_tree(self, entity_name: str) -> HierarchyNode | None:
        """Get all descendants of an entity as a nested tree.

        Computes tree by scanning all entities for children.

        Args:
            entity_name: Name of the org/pillar/team_group/team

        Returns:
            Nested tree structure with all descendants, or None if not found.
        """
        async with self._lock:
            if self._data is None:
                return None

            if self._use_stable_ids:
                return self._get_descendants_tree_by_id(entity_name)

            # Look up entity type
            entity_type = ""
            if entity_name in self._data.lookups.teams:
                entity_type = "team"
            elif entity_name in self._data.lookups.orgs:
                entity_type = "org"
            elif entity_name in self._data.lookups.pillars:
                entity_type = "pillar"
            elif entity_name in self._data.lookups.team_groups:
                entity_type = "team_group"

            if not entity_type:
                return None

            # Build children map by scanning all entities
            children_map: dict[str, list[tuple[str, str]]] = {}
            all_entities: list[tuple[str, Team | Org | Pillar | TeamGroup, str]] = [
                *(
                    (name, info, "team")
                    for name, info in self._data.lookups.teams.items()
                ),
                *(
                    (name, info, "org")
                    for name, info in self._data.lookups.orgs.items()
                ),
                *(
                    (name, info, "pillar")
                    for name, info in self._data.lookups.pillars.items()
                ),
                *(
                    (name, info, "team_group")
                    for name, info in self._data.lookups.team_groups.items()
                ),
            ]

            for name, info, etype in all_entities:
                if info.parent:
                    if info.parent.name not in children_map:
                        children_map[info.parent.name] = []
                    children_map[info.parent.name].append((name, etype))

            def build_node(name: str, type_: str, visited: set[str]) -> HierarchyNode:
                if name in visited:
                    return HierarchyNode(name=name, type=type_, children=())
                visited.add(name)
                children = children_map.get(name, [])
                child_nodes = tuple(build_node(n, t, visited) for n, t in children)
                return HierarchyNode(name=name, type=type_, children=child_nodes)

            return build_node(entity_name, entity_type, set())

    def _get_descendants_tree_by_id(self, entity_name: str) -> HierarchyNode | None:
        """Build the descendants tree using stable-ID edges. Caller holds lock."""
        entity_type = self._get_entity_type(entity_name)
        if not entity_type:
            return None
        start_id = self._id_by_name_type.get(
            _NameTypeKey(entity_name, EntityType(entity_type)), ""
        )
        if not start_id:
            return None

        def build_node(stable_id: str, visited: set[str]) -> HierarchyNode:
            ref = self._entity_by_id[stable_id]
            if stable_id in visited:
                return HierarchyNode(
                    name=ref.name, type=ref.type, stable_id=ref.stable_id, children=()
                )
            visited.add(stable_id)
            child_ids = sorted(
                self._children_by_id.get(stable_id, []),
                key=lambda cid: (
                    self._entity_by_id[cid].name,
                    self._entity_by_id[cid].type,
                ),
            )
            child_nodes = tuple(build_node(cid, visited) for cid in child_ids)
            return HierarchyNode(
                name=ref.name,
                type=ref.type,
                stable_id=ref.stable_id,
                children=child_nodes,
            )

        return build_node(start_id, set())

    async def get_user_organizations(self, slack_user_id: str) -> list[OrgInfo]:
        """Get the complete organizational hierarchy a Slack user belongs to."""
        async with self._lock:
            if self._data is None or not self._data.indexes.membership.membership_index:
                return []

            uid = self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(
                slack_user_id, ""
            )
            if not uid:
                return []

            if self._use_stable_ids:
                return self._user_organizations_by_id(uid)

            memberships = self._data.indexes.membership.membership_index.get(uid, ())
            result: list[OrgInfo] = []
            # Legacy mode: dedupe by (name, type). Names are not unique across
            # types, so keying on name alone would drop a legitimately distinct
            # entity (e.g. a team_group sharing a team's name) from the result.
            seen: set[_NameTypeKey] = set()

            for m in memberships:
                if m.type == MembershipType.ORG:
                    key = _NameTypeKey(m.name, EntityType.ORG)
                    if key not in seen:
                        result.append(
                            OrgInfo(name=m.name, type=OrgInfoType.ORGANIZATION)
                        )
                        seen.add(key)
                elif m.type == MembershipType.TEAM:
                    key = _NameTypeKey(m.name, EntityType.TEAM)
                    if key not in seen:
                        result.append(OrgInfo(name=m.name, type=OrgInfoType.TEAM))
                        seen.add(key)

                    hierarchy_path = self._get_hierarchy_path(m.name, EntityType.TEAM)
                    for entry in hierarchy_path[1:]:
                        # Free-form index type: skip unknown/empty rather than
                        # raising, matching Go.
                        entry_type = _to_entity_type(entry.type.lower())
                        if entry_type is None:
                            continue
                        entry_key = _NameTypeKey(entry.name, entry_type)
                        if entry_key not in seen:
                            result.append(
                                OrgInfo(
                                    name=entry.name,
                                    type=_ancestor_org_info_type(entry_type),
                                    stable_id=entry.stable_id,
                                )
                            )
                            seen.add(entry_key)

            return result

    def _user_organizations_by_id(self, uid: str) -> list[OrgInfo]:
        """Resolve a user's organizations by stable ID. Caller must hold lock.

        Each membership is resolved through its ``stable_id`` (the canonical
        identity), team ancestry is walked by ``parent_id``, and results are
        deduplicated by stable ID. Used only when ``_use_stable_ids`` is true.
        """
        assert self._data is not None
        memberships = self._data.indexes.membership.membership_index.get(uid, ())
        result: list[OrgInfo] = []
        seen: set[str] = set()

        for m in memberships:
            if m.type not in (MembershipType.ORG, MembershipType.TEAM):
                continue

            stable_id = m.stable_id
            if not stable_id:
                etype = _to_entity_type(m.type)
                if etype is not None:
                    stable_id = self._id_by_name_type.get(
                        _NameTypeKey(m.name, etype), ""
                    )
            ref = self._entity_by_id.get(stable_id)
            if ref is None:
                continue

            if stable_id not in seen:
                seen.add(stable_id)
                direct_type = (
                    OrgInfoType.ORGANIZATION
                    if m.type == MembershipType.ORG
                    else OrgInfoType.TEAM
                )
                result.append(
                    OrgInfo(name=ref.name, type=direct_type, stable_id=ref.stable_id)
                )

            if m.type != MembershipType.TEAM:
                continue
            # Walk ancestors with a per-walk visited set. Using the shared seen
            # set as the stop condition would halt at an ancestor already
            # recorded by an earlier (e.g. direct org) membership and drop its
            # higher ancestors. visited also terminates cyclic parent links.
            visited: set[str] = set()
            parent_id = ref.parent_id
            while parent_id and parent_id not in visited:
                visited.add(parent_id)
                parent = self._entity_by_id.get(parent_id)
                if parent is None:
                    break
                if parent_id not in seen:
                    seen.add(parent_id)
                    result.append(
                        OrgInfo(
                            name=parent.name,
                            type=_ancestor_org_info_type(parent.type),
                            stable_id=parent.stable_id,
                        )
                    )
                parent_id = parent.parent_id

        return result

    async def get_all_employees(self) -> list[Employee]:
        """Get all employees."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.employees.values())

    async def get_all_teams(self) -> list[Team]:
        """Get all teams."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.teams.values())

    async def get_all_orgs(self) -> list[Org]:
        """Get all organizations."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.orgs.values())

    async def get_all_pillars(self) -> list[Pillar]:
        """Get all pillars."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.pillars.values())

    async def get_all_team_groups(self) -> list[TeamGroup]:
        """Get all team groups."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.team_groups.values())

    async def get_all_components(self) -> list[Component]:
        """Get all components."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.components.values())

    async def get_all_component_names(self) -> list[str]:
        """Get all component names."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.components.keys())

    async def get_teams_for_component(
        self, component_name: str
    ) -> list[ComponentOwnerInfo]:
        """Get all teams/entities that own a component.

        Args:
            component_name: Component name to look up

        Returns:
            List of owner entities with ownership types.
        """
        async with self._lock:
            if self._data is None:
                return []
            owners = self._data.indexes.component_ownership.component_owners.get(
                component_name, ()
            )
            return list(owners)

    async def get_components_for_team(self, team_name: str) -> list[ComponentOwnership]:
        """Get all components owned by a team.

        Uses the team's component_roles list for O(1) team lookup, then
        resolves ownership types from the component_ownership index.

        Args:
            team_name: Team name to look up

        Returns:
            List of ComponentOwnership with component name and ownership types.
        """
        async with self._lock:
            if self._data is None:
                return []
            team = self._data.lookups.teams.get(team_name)
            if not team:
                return []
            result: list[ComponentOwnership] = []
            for cr in team.group.component_roles:
                ownership_types: tuple[str, ...] = ()
                owners = self._data.indexes.component_ownership.component_owners.get(
                    cr, ()
                )
                for owner in owners:
                    if owner.name == team_name:
                        ownership_types = owner.ownership_types
                        break
                result.append(
                    ComponentOwnership(
                        component=cr,
                        ownership_types=ownership_types,
                    )
                )
            return result

    async def get_all_team_names(self) -> list[str]:
        """Get all team names."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.teams.keys())

    async def get_all_org_names(self) -> list[str]:
        """Get all organization names."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.orgs.keys())

    async def get_all_pillar_names(self) -> list[str]:
        """Get all pillar names."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.pillars.keys())

    async def get_all_team_group_names(self) -> list[str]:
        """Get all team group names."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.team_groups.keys())

    async def get_all_employee_uids(self) -> list[str]:
        """Get all employee UIDs in the system."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.lookups.employees.keys())

    async def get_team_members(self, team_name: str) -> list[Employee]:
        """Get all members of a team."""
        async with self._lock:
            if self._data is None:
                return []
            team = self._data.lookups.teams.get(team_name)
            if not team:
                return []
            return [
                emp
                for uid in team.group.resolved_people_uid_list
                if (emp := self._data.lookups.employees.get(uid))
            ]

    async def get_org_members(self, org_name: str) -> list[Employee]:
        """Get all members of an organization."""
        async with self._lock:
            if self._data is None:
                return []
            org = self._data.lookups.orgs.get(org_name)
            if not org:
                return []
            return [
                emp
                for uid in org.group.resolved_people_uid_list
                if (emp := self._data.lookups.employees.get(uid))
            ]

    def get_version(self) -> DataVersion:
        """Get the current data version (sync - no lock needed for read)."""
        return self._version

    def get_data_version(self) -> str:
        """Get the producer-side version string of the loaded index.

        Returns ``metadata.data_version``, or "" if no data is loaded.
        """
        if self._data is None:
            return ""
        return self._data.metadata.data_version

    def get_generated_at(self) -> str:
        """Get the producer-side generation timestamp of the loaded index.

        Returns ``metadata.generated_at``, or "" if no data is loaded.
        """
        if self._data is None:
            return ""
        return self._data.metadata.generated_at

    async def get_jira_projects(self) -> list[str]:
        """Get all Jira project keys."""
        async with self._lock:
            if self._data is None:
                return []
            return list(self._data.indexes.jira.project_component_owners.keys())

    async def get_jira_components(self, project: str) -> list[str]:
        """Get all components for a Jira project.

        Args:
            project: Jira project key (e.g., "OCPBUGS")

        Returns:
            List of component names. "_project_level" indicates project-level ownership.
        """
        async with self._lock:
            if self._data is None:
                return []
            components = self._data.indexes.jira.project_component_owners.get(
                project, {}
            )
            return list(components.keys())

    async def get_teams_by_jira_project(self, project: str) -> list[JiraOwnerInfo]:
        """Get all teams/entities that own any component in a Jira project.

        Args:
            project: Jira project key (e.g., "OCPBUGS")

        Returns:
            Deduplicated list of owner entities across all components.
        """
        async with self._lock:
            if self._data is None:
                return []
            components = self._data.indexes.jira.project_component_owners.get(
                project, {}
            )
            seen: set[str] = set()
            result: list[JiraOwnerInfo] = []
            for owners in components.values():
                for owner in owners:
                    if owner.name not in seen:
                        seen.add(owner.name)
                        result.append(owner)
            return result

    async def get_teams_by_jira_component(
        self, project: str, component: str
    ) -> list[JiraOwnerInfo]:
        """Get teams/entities that own a specific Jira component.

        Args:
            project: Jira project key (e.g., "OCPBUGS")
            component: Component name (or "_project_level" for project ownership)

        Returns:
            List of owner entities for the component.
        """
        async with self._lock:
            if self._data is None:
                return []
            components = self._data.indexes.jira.project_component_owners.get(
                project, {}
            )
            owners = components.get(component, ())
            return list(owners)

    async def get_jira_ownership_for_team(self, team_name: str) -> list[dict[str, str]]:
        """Get all Jira projects and components owned by a team.

        Args:
            team_name: Team name to look up

        Returns:
            List of dicts with "project" and "component" keys.
        """
        async with self._lock:
            if self._data is None:
                return []
            result: list[dict[str, str]] = []
            for (
                project,
                components,
            ) in self._data.indexes.jira.project_component_owners.items():
                for component, owners in components.items():
                    for owner in owners:
                        if owner.name == team_name:
                            result.append({"project": project, "component": component})
                            break
            return result

    async def get_context_for_team(
        self, team_name: str
    ) -> list[ContextItemInfo]:
        """Get resolved context items for a team (including inherited)."""
        async with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []
            team = self._data.lookups.teams.get(team_name)
            if team is None:
                return []
            return list(team.group.resolved_context)

    async def get_context_for_entity(
        self, entity_name: str, entity_type: str = "team"
    ) -> list[ContextItemInfo]:
        """Get resolved context items for any entity type."""
        async with self._lock:
            if self._data is None:
                return []
            entity = self._get_entity_by_type(entity_name, entity_type)
            if entity is None:
                return []
            return list(entity.group.resolved_context)

    async def get_context_by_type(
        self, entity_name: str, context_type: str, entity_type: str = "team"
    ) -> list[ContextItemInfo]:
        """Get resolved context items filtered by a specific context type."""
        async with self._lock:
            if self._data is None:
                return []
            entity = self._get_entity_by_type(entity_name, entity_type)
            if entity is None:
                return []
            return [
                item
                for item in entity.group.resolved_context
                if context_type in item.types
            ]

    async def get_all_context_types_for_entity(
        self, entity_name: str, entity_type: str = "team"
    ) -> list[str]:
        """Get distinct context types available for an entity."""
        async with self._lock:
            if self._data is None:
                return []
            entity = self._get_entity_by_type(entity_name, entity_type)
            if entity is None:
                return []
            seen: set[str] = set()
            result: list[str] = []
            for item in entity.group.resolved_context:
                for t in item.types:
                    if t not in seen:
                        seen.add(t)
                        result.append(t)
            return result

    async def get_context_type_descriptions(self) -> dict[str, str]:
        """Get the description registry for all context types."""
        async with self._lock:
            if self._data is None:
                return {}
            return dict(self._data.metadata.context_type_descriptions)


async def _async_retry_with_backoff(
    operation: Callable[[], Awaitable[_T]],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = DEFAULT_RETRY_BACKOFF,
    operation_name: str = "operation",
) -> _T:
    """Execute an async operation with exponential backoff retry."""
    logger = get_logger()
    delay = initial_delay
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except VersionNotAvailableError:
            # A permanently-gone version is not a transient failure; don't retry.
            raise
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

    raise GCSError(
        f"{operation_name} failed after {max_retries + 1} attempts: {last_error}"
    )


try:
    from google.api_core.exceptions import NotFound
    from google.cloud import storage

    _HAS_GCS = True
except ImportError:
    _HAS_GCS = False


class AsyncGCSDataSource:
    """Async GCS data source using google-cloud-storage.

    Wraps sync GCS operations in asyncio.to_thread for non-blocking I/O.

    Requires the google-cloud-storage package:
        pip install orgdatacore[gcs]

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
            ImportError: If google-cloud-storage is not installed.
            ConfigurationError: If configuration is invalid.
        """
        if not _HAS_GCS:
            raise ImportError(
                "google-cloud-storage is required for GCS support. "
                "Install it with: pip install orgdatacore[gcs]"
            )
        if not config.bucket:
            raise ConfigurationError("GCS bucket is required")
        if not config.object_path:
            raise ConfigurationError("GCS object_path is required")

        self.config = config
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the GCS client (sync)."""
        if self._client is None:
            logger = get_logger()
            logger.debug(
                "Creating GCS client", extra={"project_id": self.config.project_id}
            )

            if self.config.credentials_json:
                import json as _json

                creds_info = _json.loads(self.config.credentials_json)
                self._client = storage.Client.from_service_account_info(creds_info)
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

    async def list_versions(self) -> list[DataVersionRef]:
        """List every retained generation of the configured object.

        See GCSDataSource.list_versions. The generation number is the object's
        creation time in microseconds since the Unix epoch.

        Raises:
            GCSError: If listing fails after all retries.
        """

        async def _list() -> list[DataVersionRef]:
            def _sync_list() -> list[DataVersionRef]:
                client = self._get_client()
                blobs = client.list_blobs(
                    self.config.bucket,
                    prefix=self.config.object_path,
                    versions=True,
                )
                refs: list[DataVersionRef] = []
                for blob in blobs:
                    if blob.name != self.config.object_path:
                        continue
                    # Prefer the explicit creation timestamp; fall back to the
                    # generation number (GCS creation time in microseconds).
                    created = blob.time_created
                    if created is None:
                        created = datetime.fromtimestamp(
                            blob.generation / 1_000_000, tz=UTC
                        )
                    refs.append(
                        DataVersionRef(id=str(blob.generation), created=created)
                    )
                return refs

            return await asyncio.to_thread(_sync_list)

        return await _async_retry_with_backoff(
            _list,
            max_retries=self.max_retries,
            initial_delay=self.retry_delay,
            backoff=self.retry_backoff,
            operation_name=f"GCS list versions gs://{self.config.bucket}/{self.config.object_path}",
        )

    async def load_version(self, ref: DataVersionRef) -> BinaryIO:
        """Load a specific generation of the object.

        Raises:
            GCSError: If the id is invalid or loading fails after all retries.
        """
        try:
            generation = int(ref.id)
        except ValueError as e:
            raise GCSError(f"invalid version id {ref.id!r}: {e}") from e

        async def _download() -> BinaryIO:
            def _sync_download() -> BinaryIO:
                client = self._get_client()
                bucket = client.bucket(self.config.bucket)
                blob = bucket.blob(self.config.object_path, generation=generation)
                try:
                    return BytesIO(blob.download_as_bytes())
                except NotFound as e:
                    raise VersionNotAvailableError(
                        f"generation {generation} is no longer retained in "
                        f"gs://{self.config.bucket}/{self.config.object_path}"
                    ) from e

            return await asyncio.to_thread(_sync_download)

        return await _async_retry_with_backoff(
            _download,
            max_retries=self.max_retries,
            initial_delay=self.retry_delay,
            backoff=self.retry_backoff,
            operation_name=f"GCS download generation {generation} gs://{self.config.bucket}/{self.config.object_path}",
        )

    async def watch(
        self, callback: Callable[[], Awaitable[Exception | None]]
    ) -> Exception | None:
        """Monitor for changes and call async callback when data is updated.

        This coroutine blocks until cancelled. The caller should wrap it in
        asyncio.create_task() and cancel the task to stop watching.

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
            logger.error(
                "Failed to initialize async GCS watcher", extra={"error": str(e)}
            )
            return GCSError(f"Failed to initialize GCS watcher: {e}")

        interval = self.config.check_interval.total_seconds()

        try:
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
                            logger.error(
                                "Async reload callback failed",
                                extra={"error": str(err)},
                            )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(
                        "Async GCS watcher check failed", extra={"error": str(e)}
                    )
        except asyncio.CancelledError:
            logger.info("Async GCS watcher cancelled")

        return None

    def __str__(self) -> str:
        """Return a description of this data source."""
        return f"gs://{self.config.bucket}/{self.config.object_path} (async)"
