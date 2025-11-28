"""Async service implementation for orgdatacore.

This module provides an async-compatible version of the Service class
for use with asyncio-based frameworks like FastAPI, aiohttp, etc.

Example:
    from orgdatacore.async_service import AsyncService
    from orgdatacore.async_datasources import AsyncGCSDataSource

    async def main():
        service = AsyncService()
        source = AsyncGCSDataSource(config)
        await service.load_from_data_source(source)

        employee = await service.get_employee_by_uid("jdoe")
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, Any

from .constants import MembershipType, OrgInfoType
from .exceptions import DataLoadError
from .logging import get_logger
from .service import _parse_data
from .types import (
    Data,
    DataVersion,
    Employee,
    MembershipInfo,
    Org,
    OrgInfo,
    Pillar,
    Team,
    TeamGroup,
)


class AsyncService:
    """Async implementation of the organizational data service.

    Thread-safe and asyncio-compatible. All lookup methods are async
    to allow for non-blocking operation in async contexts.

    Example:
        service = AsyncService()
        await service.load_from_data_source(source)
        employee = await service.get_employee_by_uid("jdoe")
    """

    def __init__(self, *, data_source: Optional[Any] = None) -> None:
        """Initialize a new async organizational data service.

        Args:
            data_source: Optional async data source to load from immediately.
        """
        self._lock = asyncio.Lock()
        self._data: Optional[Data] = None
        self._version = DataVersion()
        self._init_source = data_source

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

        Args:
            source: Async data source to watch.

        Raises:
            DataLoadError: If initial load fails.
        """
        logger = get_logger()

        # Perform initial load
        await self.load_from_data_source(source)

        # Define callback for reload
        async def callback() -> Optional[Exception]:
            try:
                logger.info("Reloading data from async source", extra={"source": str(source)})
                await self.load_from_data_source(source)
                return None
            except Exception as e:
                logger.error("Failed to reload data", extra={"source": str(source), "error": str(e)})
                return e

        # Start watcher if source supports it
        if hasattr(source, "watch"):
            logger.info("Starting async data source watcher", extra={"source": str(source)})
            if asyncio.iscoroutinefunction(source.watch):
                err = await source.watch(callback)
            else:
                err = source.watch(lambda: asyncio.run(callback()))
            if err:
                logger.error("Failed to start watcher", extra={"source": str(source), "error": str(err)})
                raise err

    def is_healthy(self) -> bool:
        """Check if the service has data loaded."""
        return self._data is not None

    def is_ready(self) -> bool:
        """Check if the service is ready to serve requests."""
        if self._data is None:
            return False
        return self._data.lookups is not None and self._data.indexes is not None

    # Async lookup methods

    async def get_employee_by_uid(self, uid: str) -> Optional[Employee]:
        """Get an employee by their UID."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.employees.get(uid)

    async def get_employee_by_email(self, email: str) -> Optional[Employee]:
        """Get an employee by their email address."""
        async with self._lock:
            if self._data is None:
                return None
            for emp in self._data.lookups.employees.values():
                if emp.email.lower() == email.lower():
                    return emp
            return None

    async def get_employee_by_slack_uid(self, slack_uid: str) -> Optional[Employee]:
        """Get an employee by their Slack UID."""
        async with self._lock:
            if self._data is None:
                return None
            uid = self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(slack_uid)
            if uid:
                return self._data.lookups.employees.get(uid)
            return None

    async def get_employee_by_github_id(self, github_id: str) -> Optional[Employee]:
        """Get an employee by their GitHub ID."""
        async with self._lock:
            if self._data is None:
                return None
            uid = self._data.indexes.github_id_mappings.github_id_to_uid.get(github_id)
            if uid:
                return self._data.lookups.employees.get(uid)
            return None

    async def get_team_by_name(self, name: str) -> Optional[Team]:
        """Get a team by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.teams.get(name)

    async def get_org_by_name(self, name: str) -> Optional[Org]:
        """Get an organization by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.orgs.get(name)

    async def get_pillar_by_name(self, name: str) -> Optional[Pillar]:
        """Get a pillar by name."""
        async with self._lock:
            if self._data is None:
                return None
            return self._data.lookups.pillars.get(name)

    async def get_team_group_by_name(self, name: str) -> Optional[TeamGroup]:
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

