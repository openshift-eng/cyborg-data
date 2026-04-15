"""Service implementation for orgdatacore."""

import json
import threading
from datetime import datetime, timedelta
from typing import Any, cast

from ._exceptions import DataLoadError
from ._log import get_logger
from ._types import (
    Component,
    ComponentOwnerInfo,
    ComponentOwnership,
    ComponentOwnershipIndex,
    ContextItemInfo,
    Data,
    DataSource,
    DataVersion,
    Employee,
    EscalationContactInfo,
    GitHubIDMappings,
    HierarchyNode,
    HierarchyPathEntry,
    Indexes,
    JiraIndex,
    JiraOwnerInfo,
    Lookups,
    MembershipIndex,
    MembershipInfo,
    MembershipType,
    Metadata,
    Org,
    OrgInfo,
    OrgInfoType,
    Pillar,
    SlackIDMappings,
    Team,
    TeamGroup,
)


def _parse_jira_index(jira_raw: dict[str, Any]) -> JiraIndex:
    """Parse the Jira index from raw data."""
    project_component_owners: dict[str, dict[str, tuple[JiraOwnerInfo, ...]]] = {}

    for project, components in jira_raw.items():
        if not isinstance(components, dict):
            continue
        project_component_owners[project] = {}
        components_dict = cast(dict[str, Any], components)
        for component, owners in components_dict.items():
            if isinstance(owners, list):
                owners_list = cast(list[dict[str, Any]], owners)
                project_component_owners[project][component] = tuple(
                    JiraOwnerInfo.model_validate(o) for o in owners_list
                )

    return JiraIndex(project_component_owners=project_component_owners)


def _parse_component_ownership_index(raw: dict[str, Any]) -> ComponentOwnershipIndex:
    """Parse the component ownership index from raw data."""
    component_owners: dict[str, tuple[ComponentOwnerInfo, ...]] = {}

    for component_name, owners in raw.items():
        if isinstance(owners, list):
            owners_list = cast(list[dict[str, Any]], owners)
            component_owners[component_name] = tuple(
                ComponentOwnerInfo.model_validate(o) for o in owners_list
            )

    return ComponentOwnershipIndex(component_owners=component_owners)


def parse_data(raw_data: dict[str, Any]) -> Data:
    """Parse the complete Data structure from JSON."""
    metadata = Metadata.model_validate(raw_data.get("metadata", {}))

    lookups_raw = raw_data.get("lookups", {})
    lookups = Lookups(
        employees={
            k: Employee.model_validate(v)
            for k, v in lookups_raw.get("employees", {}).items()
        },
        teams={
            k: Team.model_validate(v) for k, v in lookups_raw.get("teams", {}).items()
        },
        orgs={k: Org.model_validate(v) for k, v in lookups_raw.get("orgs", {}).items()},
        pillars={
            k: Pillar.model_validate(v)
            for k, v in lookups_raw.get("pillars", {}).items()
        },
        team_groups={
            k: TeamGroup.model_validate(v)
            for k, v in lookups_raw.get("team_groups", {}).items()
        },
        components={
            k: Component.model_validate(v)
            for k, v in lookups_raw.get("components", {}).items()
        },
    )

    indexes_raw = raw_data.get("indexes", {})
    membership_raw = indexes_raw.get("membership", {})

    membership_index_raw = membership_raw.get("membership_index", {})
    membership_index = {
        k: tuple(MembershipInfo.model_validate(m) for m in v)
        for k, v in membership_index_raw.items()
    }

    membership = MembershipIndex(
        membership_index=membership_index,
    )

    slack_mappings_raw = indexes_raw.get("slack_id_mappings", {})
    slack_id_mappings = SlackIDMappings(
        slack_uid_to_uid=slack_mappings_raw.get("slack_uid_to_uid", {}),
    )

    github_mappings_raw = indexes_raw.get("github_id_mappings", {})
    github_id_mappings = GitHubIDMappings(
        github_id_to_uid=github_mappings_raw.get("github_id_to_uid", {}),
    )

    jira_raw = indexes_raw.get("jira", {})
    jira_index = _parse_jira_index(jira_raw)

    component_ownership_raw = indexes_raw.get("component_ownership", {})
    component_ownership = _parse_component_ownership_index(component_ownership_raw)

    indexes = Indexes(
        membership=membership,
        slack_id_mappings=slack_id_mappings,
        github_id_mappings=github_id_mappings,
        jira=jira_index,
        component_ownership=component_ownership,
    )

    return Data(
        metadata=metadata,
        lookups=lookups,
        indexes=indexes,
    )


def _validate_data(data: Data, source: DataSource) -> None:
    """Validate that required data structures are present."""
    if not data.lookups.employees:
        raise DataLoadError(f"invalid data from {source}: missing lookups.employees")
    if not data.indexes.membership.membership_index:
        raise DataLoadError(
            f"invalid data from {source}: missing indexes.membership.membership_index"
        )


class Service:
    """
    Service implements the core organizational data service.

    The service can be initialized in two ways:

    1. Lazy loading (matches Go API):
        service = Service()
        service.load_from_data_source(gcs_source)

    2. Constructor injection:
        service = Service(data_source=gcs_source)

    Both approaches are equivalent. Use constructor injection for simpler code,
    or lazy loading if you need to defer data loading.
    """

    def __init__(self, *, data_source: DataSource | None = None) -> None:
        """
        Create a new organizational data service.

        Args:
            data_source: Optional data source to load immediately.
                        If provided, data is loaded during construction.
                        Must be passed as keyword argument.
        """
        self._lock = threading.RLock()
        self._data: Data | None = None
        self._version = DataVersion()
        self._watcher_running = False
        self._stop_event = threading.Event()

        if data_source is not None:
            self.load_from_data_source(data_source)

    def load_from_data_source(self, source: DataSource) -> None:
        """Load organizational data from a data source.

        Args:
            source: Data source to load from.

        Raises:
            DataLoadError: If loading or parsing fails.
        """
        logger = get_logger()
        logger.debug("Loading data from source", extra={"source": str(source)})

        try:
            reader = source.load()
        except Exception as e:
            logger.error(
                "Failed to load from data source",
                extra={"source": str(source), "error": str(e)},
            )
            raise DataLoadError(f"failed to load from data source {source}: {e}") from e

        try:
            raw_data = json.load(reader)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON", extra={"source": str(source), "error": str(e)}
            )
            raise DataLoadError(
                f"failed to parse JSON from source {source}: {e}"
            ) from e
        finally:
            reader.close()

        try:
            org_data = parse_data(raw_data)
        except Exception as e:
            logger.error(
                "Failed to parse data structure",
                extra={"source": str(source), "error": str(e)},
            )
            raise DataLoadError(
                f"failed to parse data structure from source {source}: {e}"
            ) from e

        _validate_data(org_data, source)

        with self._lock:
            self._data = org_data
            self._version = DataVersion(
                load_time=datetime.now(),
                org_count=len(org_data.lookups.orgs),
                employee_count=len(org_data.lookups.employees),
            )

        logger.info(
            "Data loaded successfully",
            extra={
                "source": str(source),
                "employee_count": self._version.employee_count,
                "org_count": self._version.org_count,
            },
        )

    def start_data_source_watcher(self, source: DataSource) -> None:
        """Start watching a data source for changes.

        Performs initial load, then starts background watcher for hot reload.

        Args:
            source: Data source to watch.

        Raises:
            DataLoadError: If initial load fails.
            RuntimeError: If watcher is already running.
        """
        logger = get_logger()

        if self._watcher_running:
            raise RuntimeError("Watcher is already running")

        self._watcher_running = True
        self._stop_event.clear()

        try:
            self.load_from_data_source(source)

            def callback() -> Exception | None:
                if self._stop_event.is_set():
                    return None
                try:
                    logger.info(
                        "Reloading data from source", extra={"source": str(source)}
                    )
                    self.load_from_data_source(source)
                    return None
                except Exception as e:
                    logger.error(
                        "Failed to reload data",
                        extra={"source": str(source), "error": str(e)},
                    )
                    return e

            logger.info("Starting data source watcher", extra={"source": str(source)})
            err = source.watch(callback)
            if err:
                logger.error(
                    "Failed to start watcher",
                    extra={"source": str(source), "error": str(err)},
                )
                raise err
        finally:
            self._watcher_running = False

    def stop_watcher(self) -> None:
        """Stop the data source watcher if running."""
        self._stop_event.set()
        self._watcher_running = False

    def is_healthy(self) -> bool:
        """Check if the service is healthy and has data loaded."""
        with self._lock:
            return self._data is not None

    def is_ready(self) -> bool:
        """Check if the service is ready to serve requests."""
        with self._lock:
            if self._data is None:
                return False
            # Data has lookups and indexes (always present when data is loaded)
            return bool(self._data.lookups.employees)

    def get_version(self) -> DataVersion:
        """Get the current data version."""
        with self._lock:
            return self._version

    def get_data_age(self) -> timedelta:
        """Get the duration since data was last loaded.

        Returns:
            timedelta since last load, or timedelta(0) if no data loaded.
        """
        with self._lock:
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
        with self._lock:
            if self._data is None or self._version.load_time == datetime.min:
                return True
            return (datetime.now() - self._version.load_time) > max_age

    def get_employee_by_uid(self, uid: str) -> Employee | None:
        """Get an employee by UID."""
        with self._lock:
            if self._data is None or not self._data.lookups.employees:
                return None
            return self._data.lookups.employees.get(uid)

    def get_employee_by_email(self, email: str) -> Employee | None:
        """Get an employee by their email address."""
        with self._lock:
            if self._data is None or not self._data.lookups.employees:
                return None
            email_lower = email.lower()
            for emp in self._data.lookups.employees.values():
                if emp.email.lower() == email_lower:
                    return emp
            return None

    def get_employee_by_slack_id(self, slack_id: str) -> Employee | None:
        """Get an employee by Slack ID."""
        with self._lock:
            if (
                self._data is None
                or not self._data.indexes.slack_id_mappings.slack_uid_to_uid
                or not self._data.lookups.employees
            ):
                return None

            uid = self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(
                slack_id, ""
            )
            if not uid:
                return None

            return self._data.lookups.employees.get(uid)

    def get_employee_by_github_id(self, github_id: str) -> Employee | None:
        """Get an employee by GitHub ID."""
        with self._lock:
            if (
                self._data is None
                or not self._data.indexes.github_id_mappings.github_id_to_uid
                or not self._data.lookups.employees
            ):
                return None

            uid = self._data.indexes.github_id_mappings.github_id_to_uid.get(
                github_id, ""
            )
            if not uid:
                return None

            return self._data.lookups.employees.get(uid)

    def get_manager_for_employee(self, uid: str) -> Employee | None:
        """Get the manager for a given employee UID."""
        with self._lock:
            if self._data is None or not self._data.lookups.employees:
                return None

            emp = self._data.lookups.employees.get(uid)
            if not emp or not emp.manager_uid:
                return None

            return self._data.lookups.employees.get(emp.manager_uid)

    def get_team_by_name(self, team_name: str) -> Team | None:
        """Get a team by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return None
            return self._data.lookups.teams.get(team_name)

    def get_team_escalation(self, team_name: str) -> list[EscalationContactInfo]:
        """Get the escalation contacts for a team.

        Args:
            team_name: The team name to look up.

        Returns:
            Ordered list of escalation contacts, or empty list if team
            not found or has no escalation data.
        """
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []
            team = self._data.lookups.teams.get(team_name)
            if team is None:
                return []
            return list(team.group.escalation)

    def get_org_by_name(self, org_name: str) -> Org | None:
        """Get an organization by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.orgs:
                return None
            return self._data.lookups.orgs.get(org_name)

    def get_pillar_by_name(self, pillar_name: str) -> Pillar | None:
        """Get a pillar by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.pillars:
                return None
            return self._data.lookups.pillars.get(pillar_name)

    def get_team_group_by_name(self, team_group_name: str) -> TeamGroup | None:
        """Get a team group by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.team_groups:
                return None
            return self._data.lookups.team_groups.get(team_group_name)

    def get_component_by_name(self, component_name: str) -> Component | None:
        """Get a component by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.components:
                return None
            return self._data.lookups.components.get(component_name)

    def get_all_components(self) -> list[Component]:
        """Get all components in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.components:
                return []
            return list(self._data.lookups.components.values())

    def get_all_component_names(self) -> list[str]:
        """Get all component names in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.components:
                return []
            return list(self._data.lookups.components.keys())

    def get_teams_for_component(self, component_name: str) -> list[ComponentOwnerInfo]:
        """Get all teams/entities that own a component.

        Args:
            component_name: Component name to look up

        Returns:
            List of owner entities with ownership types.
        """
        with self._lock:
            if self._data is None:
                return []
            owners = self._data.indexes.component_ownership.component_owners.get(
                component_name, ()
            )
            return list(owners)

    def get_components_for_team(self, team_name: str) -> list[ComponentOwnership]:
        """Get all components owned by a team.

        Uses the team's component_roles list for O(1) team lookup, then
        resolves ownership types from the component_ownership index.

        Args:
            team_name: Team name to look up

        Returns:
            List of ComponentOwnership with component name and ownership types.
        """
        with self._lock:
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

    def get_teams_for_uid(self, uid: str) -> list[str]:
        """Get all teams a UID is a member of."""
        with self._lock:
            return self._get_teams_for_uid(uid)

    def _get_teams_for_uid(self, uid: str) -> list[str]:
        """Internal: Get all teams a UID is a member of. Caller must hold lock."""
        if self._data is None or not self._data.indexes.membership.membership_index:
            return []

        memberships = self._data.indexes.membership.membership_index.get(uid, ())
        teams: list[str] = []
        for membership in memberships:
            if membership.type == MembershipType.TEAM:
                teams.append(membership.name)
        return teams

    def get_teams_for_slack_id(self, slack_id: str) -> list[str]:
        """Get all teams a Slack user is a member of."""
        with self._lock:
            uid = self._get_uid_from_slack_id(slack_id)
            if not uid:
                return []
            return self._get_teams_for_uid(uid)

    def get_team_members(self, team_name: str) -> list[Employee]:
        """Get all members of a team."""
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []

            team = self._data.lookups.teams.get(team_name)
            if not team:
                return []

            return [
                emp
                for uid in team.group.resolved_people_uid_list
                if (emp := self._data.lookups.employees.get(uid))
            ]

    def is_employee_in_team(self, uid: str, team_name: str) -> bool:
        """Check if an employee is in a specific team."""
        with self._lock:
            return self._is_employee_in_team(uid, team_name)

    def _is_employee_in_team(self, uid: str, team_name: str) -> bool:
        """Internal: Check if an employee is in a specific team. Caller must hold lock."""
        teams = self._get_teams_for_uid(uid)
        return team_name in teams

    def is_slack_user_in_team(self, slack_id: str, team_name: str) -> bool:
        """Check if a Slack user is in a specific team."""
        with self._lock:
            uid = self._get_uid_from_slack_id(slack_id)
            if not uid:
                return False
            return self._is_employee_in_team(uid, team_name)

    def is_employee_in_org(self, uid: str, org_name: str) -> bool:
        """Check if an employee is in a specific organization."""
        with self._lock:
            return self._is_employee_in_org(uid, org_name)

    def _is_employee_in_org(self, uid: str, org_name: str) -> bool:
        """Internal: Check if an employee is in a specific organization. Caller must hold lock."""
        if self._data is None or not self._data.indexes.membership.membership_index:
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

    def is_slack_user_in_org(self, slack_id: str, org_name: str) -> bool:
        """Check if a Slack user is in a specific organization."""
        with self._lock:
            uid = self._get_uid_from_slack_id(slack_id)
            if not uid:
                return False
            return self._is_employee_in_org(uid, org_name)

    def get_user_organizations(self, slack_user_id: str) -> list[OrgInfo]:
        """Get the complete organizational hierarchy a Slack user belongs to."""
        with self._lock:
            if self._data is None or not self._data.indexes.membership.membership_index:
                return []

            uid = self._get_uid_from_slack_id(slack_user_id)
            if not uid:
                return []

            memberships = self._data.indexes.membership.membership_index.get(uid, ())
            orgs: list[OrgInfo] = []
            seen: set[str] = set()

            for membership in memberships:
                if membership.type == MembershipType.ORG:
                    if membership.name not in seen:
                        orgs.append(
                            OrgInfo(name=membership.name, type=OrgInfoType.ORGANIZATION)
                        )
                        seen.add(membership.name)

                elif membership.type == MembershipType.TEAM:
                    if membership.name not in seen:
                        orgs.append(
                            OrgInfo(name=membership.name, type=OrgInfoType.TEAM)
                        )
                        seen.add(membership.name)

                    hierarchy_path = self._get_hierarchy_path(membership.name, "team")
                    self._add_hierarchy_path_items(orgs, seen, tuple(hierarchy_path))

            return orgs

    def _add_hierarchy_path_items(
        self,
        orgs: list[OrgInfo],
        seen: set[str],
        hierarchy_path: tuple[HierarchyPathEntry, ...],
    ) -> None:
        """Add hierarchy path items to the orgs list, avoiding duplicates."""
        type_to_org_info_type = {
            "org": OrgInfoType.ORGANIZATION,
            "pillar": OrgInfoType.PILLAR,
            "team_group": OrgInfoType.TEAM_GROUP,
            "team": OrgInfoType.PARENT_TEAM,
        }
        for entry in hierarchy_path[1:]:
            if entry.name not in seen:
                org_type = type_to_org_info_type.get(
                    entry.type.lower(), OrgInfoType.ORGANIZATION
                )
                orgs.append(OrgInfo(name=entry.name, type=org_type))
                seen.add(entry.name)

    def _get_uid_from_slack_id(self, slack_id: str) -> str:
        """Get the UID for a given Slack ID."""
        if (
            self._data is None
            or not self._data.indexes.slack_id_mappings.slack_uid_to_uid
        ):
            return ""
        return self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(slack_id, "")

    def get_user_memberships(self, uid: str) -> list[MembershipInfo]:
        """Get all memberships for a user.

        Args:
            uid: The employee UID.

        Returns:
            List of membership entries, or empty list if not found.
        """
        with self._lock:
            if self._data is None or not self._data.indexes.membership.membership_index:
                return []
            return list(self._data.indexes.membership.membership_index.get(uid, ()))

    def get_user_teams(self, uid: str) -> list[str]:
        """Get team names for a user.

        Args:
            uid: The employee UID.

        Returns:
            List of team names the user belongs to.
        """
        with self._lock:
            return self._get_teams_for_uid(uid)

    def get_all_employees(self) -> list[Employee]:
        """Get all employees in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.employees:
                return []
            return list(self._data.lookups.employees.values())

    def get_all_teams(self) -> list[Team]:
        """Get all teams in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []
            return list(self._data.lookups.teams.values())

    def get_all_orgs(self) -> list[Org]:
        """Get all organizations in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.orgs:
                return []
            return list(self._data.lookups.orgs.values())

    def get_all_pillars(self) -> list[Pillar]:
        """Get all pillars in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.pillars:
                return []
            return list(self._data.lookups.pillars.values())

    def get_all_team_groups(self) -> list[TeamGroup]:
        """Get all team groups in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.team_groups:
                return []
            return list(self._data.lookups.team_groups.values())

    def get_org_members(self, org_name: str) -> list[Employee]:
        """Get all members of an organization.

        Args:
            org_name: The organization name.

        Returns:
            List of employees in the organization.
        """
        with self._lock:
            if self._data is None or not self._data.lookups.orgs:
                return []
            org = self._data.lookups.orgs.get(org_name)
            if not org:
                return []
            return [
                emp
                for uid in org.group.resolved_people_uid_list
                if (emp := self._data.lookups.employees.get(uid))
            ]

    def get_all_employee_uids(self) -> list[str]:
        """Get all employee UIDs in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.employees:
                return []
            return list(self._data.lookups.employees.keys())

    def get_all_team_names(self) -> list[str]:
        """Get all team names in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []
            return list(self._data.lookups.teams.keys())

    def get_all_org_names(self) -> list[str]:
        """Get all organization names in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.orgs:
                return []
            return list(self._data.lookups.orgs.keys())

    def get_all_pillar_names(self) -> list[str]:
        """Get all pillar names in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.pillars:
                return []
            return list(self._data.lookups.pillars.keys())

    def get_all_team_group_names(self) -> list[str]:
        """Get all team group names in the system."""
        with self._lock:
            if self._data is None or not self._data.lookups.team_groups:
                return []
            return list(self._data.lookups.team_groups.keys())

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

    def _get_entity_type(self, entity_name: str) -> str:
        """Look up entity type by scanning lookups."""
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

    def get_hierarchy_path(
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
        with self._lock:
            return self._get_hierarchy_path(entity_name, entity_type)

    def _get_hierarchy_path(
        self, entity_name: str, entity_type: str = "team"
    ) -> list[HierarchyPathEntry]:
        """Internal: Get hierarchy path. Caller must hold lock."""
        if self._data is None:
            return []

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

    def get_descendants_tree(self, entity_name: str) -> HierarchyNode | None:
        """Get all descendants of an entity as a nested tree.

        Computes tree by scanning all entities for children.

        Args:
            entity_name: Name of the org/pillar/team_group/team

        Returns:
            Nested tree structure with all descendants, or None if not found.
        """
        with self._lock:
            if self._data is None:
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

            entity_type = self._get_entity_type(entity_name)
            if not entity_type:
                return None

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

    def get_jira_projects(self) -> list[str]:
        """Get all Jira project keys."""
        with self._lock:
            if self._data is None:
                return []
            return list(self._data.indexes.jira.project_component_owners.keys())

    def get_jira_components(self, project: str) -> list[str]:
        """Get all components for a Jira project.

        Args:
            project: Jira project key (e.g., "OCPBUGS")

        Returns:
            List of component names. "_project_level" indicates project-level ownership.
        """
        with self._lock:
            if self._data is None:
                return []
            components = self._data.indexes.jira.project_component_owners.get(
                project, {}
            )
            return list(components.keys())

    def get_teams_by_jira_project(self, project: str) -> list[JiraOwnerInfo]:
        """Get all teams/entities that own any component in a Jira project.

        Args:
            project: Jira project key (e.g., "OCPBUGS")

        Returns:
            Deduplicated list of owner entities across all components.
        """
        with self._lock:
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

    def get_teams_by_jira_component(
        self, project: str, component: str
    ) -> list[JiraOwnerInfo]:
        """Get teams/entities that own a specific Jira component.

        Args:
            project: Jira project key (e.g., "OCPBUGS")
            component: Component name (or "_project_level" for project ownership)

        Returns:
            List of owner entities for the component.
        """
        with self._lock:
            if self._data is None:
                return []
            components = self._data.indexes.jira.project_component_owners.get(
                project, {}
            )
            owners = components.get(component, ())
            return list(owners)

    def get_jira_ownership_for_team(self, team_name: str) -> list[dict[str, str]]:
        """Get all Jira projects and components owned by a team.

        Args:
            team_name: Team name to look up

        Returns:
            List of dicts with "project" and "component" keys.
        """
        with self._lock:
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

    def get_context_for_team(self, team_name: str) -> list[ContextItemInfo]:
        """Get resolved context items for a team (including inherited).

        Args:
            team_name: The team name to look up.

        Returns:
            List of resolved context items, or empty list if not found.
        """
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []
            team = self._data.lookups.teams.get(team_name)
            if team is None:
                return []
            return list(team.group.resolved_context)

    def get_context_for_entity(
        self, entity_name: str, entity_type: str = "team"
    ) -> list[ContextItemInfo]:
        """Get resolved context items for any entity type.

        Args:
            entity_name: Name of the entity.
            entity_type: Type of entity ("team", "org", "pillar", "team_group").

        Returns:
            List of resolved context items, or empty list if not found.
        """
        with self._lock:
            if self._data is None:
                return []
            entity = self._get_entity_by_type(entity_name, entity_type)
            if entity is None:
                return []
            return list(entity.group.resolved_context)

    def get_context_by_type(
        self, entity_name: str, context_type: str, entity_type: str = "team"
    ) -> list[ContextItemInfo]:
        """Get resolved context items filtered by a specific context type.

        Args:
            entity_name: Name of the entity.
            context_type: Context type to filter by (e.g., "release_framework").
            entity_type: Type of entity ("team", "org", "pillar", "team_group").

        Returns:
            List of matching context items, or empty list if not found.
        """
        with self._lock:
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

    def get_all_context_types_for_entity(
        self, entity_name: str, entity_type: str = "team"
    ) -> list[str]:
        """Get distinct context types available for an entity.

        Args:
            entity_name: Name of the entity.
            entity_type: Type of entity ("team", "org", "pillar", "team_group").

        Returns:
            List of distinct context type strings.
        """
        with self._lock:
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

    def get_context_type_descriptions(self) -> dict[str, str]:
        """Get the description registry for all context types.

        Returns a dict mapping context type enum values to their human-readable
        descriptions, sourced from the index metadata.
        """
        with self._lock:
            if self._data is None:
                return {}
            return dict(self._data.metadata.context_type_descriptions)
