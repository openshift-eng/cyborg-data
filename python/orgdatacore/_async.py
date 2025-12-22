# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
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
from ._service import parse_data
from ._types import (
    Component,
    Data,
    DataVersion,
    Employee,
    GCSConfig,
    HierarchyNode,
    HierarchyPathEntry,
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
            org_data = parse_data(raw_data)
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
        # Data has lookups and indexes (always present when data is loaded)
        return bool(self._data.lookups.employees)

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

    async def get_component_by_name(self, name: str) -> Component | None:
        """Get a component by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.components.get(name)

    async def get_user_memberships(self, uid: str) -> tuple[MembershipInfo, ...]:
        """Get all memberships for a user."""
        async with self._lock:
            if self._data is None:
                return ()
            return self._data.indexes.membership.membership_index.get(uid, ())

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
            return self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(slack_id, "")

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
                if membership.type == MembershipType.ORG and membership.name == org_name:
                    return True
                elif membership.type == MembershipType.TEAM:
                    hierarchy_path = self._get_hierarchy_path(membership.name, "team")
                    for entry in hierarchy_path:
                        if entry.type == "org" and entry.name == org_name:
                            return True

            return False

    async def is_slack_user_in_org(self, slack_id: str, org_name: str) -> bool:
        """Check if a Slack user is in a specific organization."""
        uid = await self._get_uid_from_slack_id(slack_id)
        if not uid:
            return False
        return await self.is_employee_in_org(uid, org_name)

    def _get_entity_by_type(
            self, entity_name: str, entity_type: str
    ) -> Team | Org | Pillar | TeamGroup | None:
        """Get entity from lookups by name and type."""
        if self._data is None:
            return None
        type_to_lookup = {
            "team": self._data.lookups.teams,
            "org": self._data.lookups.orgs,
            "pillar": self._data.lookups.pillars,
            "team_group": self._data.lookups.team_groups,
        }
        lookup = type_to_lookup.get(entity_type.lower())
        if not lookup:
            return None
        return lookup.get(entity_name)

    def _get_hierarchy_path(self, entity_name: str, entity_type: str) -> list[HierarchyPathEntry]:
        """Compute hierarchy path by walking parent references."""
        if self._data is None:
            return []

        entity = self._get_entity_by_type(entity_name, entity_type)
        if entity is None:
            return []

        path = [HierarchyPathEntry(name=entity_name, type=entity_type)]
        visited = {entity_name}
        current = entity

        while current and current.parent:
            parent = current.parent
            if parent.name in visited:
                break
            visited.add(parent.name)
            path.append(HierarchyPathEntry(name=parent.name, type=parent.type))
            current = self._get_entity_by_type(parent.name, parent.type)

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

            # Look up entity type
            entity_type = ""
            for type_name, lookup in [
                ("team", self._data.lookups.teams),
                ("org", self._data.lookups.orgs),
                ("pillar", self._data.lookups.pillars),
                ("team_group", self._data.lookups.team_groups),
            ]:
                if entity_name in lookup:
                    entity_type = type_name
                    break

            if not entity_type:
                return None

            # Build children map by scanning all entities
            children_map: dict[str, list[tuple[str, str]]] = {}
            all_entities: list[tuple[str, Team | Org | Pillar | TeamGroup, str]] = [
                *((name, info, "team") for name, info in self._data.lookups.teams.items()),
                *((name, info, "org") for name, info in self._data.lookups.orgs.items()),
                *((name, info, "pillar") for name, info in self._data.lookups.pillars.items()),
                *((name, info, "team_group") for name, info in self._data.lookups.team_groups.items()),
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

    async def get_user_organizations(self, uid: str) -> tuple[OrgInfo, ...]:
        """Get organization info for a user."""
        async with self._lock:
            if self._data is None:
                return ()

            memberships = self._data.indexes.membership.membership_index.get(uid, ())
            result: list[OrgInfo] = []
            seen: set[str] = set()

            type_to_org_info_type = {
                "org": OrgInfoType.ORGANIZATION,
                "pillar": OrgInfoType.PILLAR,
                "team_group": OrgInfoType.TEAM_GROUP,
                "team": OrgInfoType.PARENT_TEAM,
            }

            for m in memberships:
                if m.type == MembershipType.ORG:
                    if m.name not in seen:
                        result.append(OrgInfo(name=m.name, type=OrgInfoType.ORGANIZATION))
                        seen.add(m.name)
                elif m.type == MembershipType.TEAM:
                    if m.name not in seen:
                        result.append(OrgInfo(name=m.name, type=OrgInfoType.TEAM))
                        seen.add(m.name)

                    hierarchy_path = self._get_hierarchy_path(m.name, "team")
                    for entry in hierarchy_path[1:]:
                        if entry.name not in seen:
                            org_type = type_to_org_info_type.get(entry.type.lower(), OrgInfoType.ORGANIZATION)
                            result.append(OrgInfo(name=entry.name, type=org_type))
                            seen.add(entry.name)

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

    async def get_all_components(self) -> tuple[Component, ...]:
        """Get all components."""
        async with self._lock:
            if self._data is None:
                return ()
            return tuple(self._data.lookups.components.values())

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

    async def get_team_members(self, team_name: str) -> tuple[Employee, ...]:
        """Get all members of a team."""
        async with self._lock:
            if self._data is None:
                return ()
            team = self._data.lookups.teams.get(team_name)
            if not team:
                return ()
            result: list[Employee] = []
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
            result: list[Employee] = []
            for uid in org.group.resolved_people_uid_list:
                emp = self._data.lookups.employees.get(uid)
                if emp:
                    result.append(emp)
            return tuple(result)

    def get_version(self) -> DataVersion:
        """Get the current data version (sync - no lock needed for read)."""
        return self._version

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
            components = self._data.indexes.jira.project_component_owners.get(project, {})
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
            components = self._data.indexes.jira.project_component_owners.get(project, {})
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
            components = self._data.indexes.jira.project_component_owners.get(project, {})
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
            for project, components in self._data.indexes.jira.project_component_owners.items():
                for component, owners in components.items():
                    for owner in owners:
                        if owner.name == team_name:
                            result.append({"project": project, "component": component})
                            break
            return result


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
