"""Service implementation for orgdatacore."""

import json
import threading
from datetime import datetime
from typing import Optional, Any

from .constants import MembershipType, OrgInfoType
from .exceptions import DataLoadError
from .interface import DataSource
from .logging import get_logger
from .types import (
    Data,
    DataVersion,
    Employee,
    Team,
    Org,
    Pillar,
    TeamGroup,
    OrgInfo,
    Metadata,
    Lookups,
    Indexes,
    MembershipIndex,
    MembershipInfo,
    RelationshipInfo,
    Ancestry,
    SlackIDMappings,
    GitHubIDMappings,
    Group,
    GroupType,
    SlackConfig,
    ChannelInfo,
    AliasInfo,
    RoleInfo,
    JiraInfo,
    RepoInfo,
    EmailInfo,
    ResourceInfo,
    ComponentRoleInfo,
)


def _parse_employee(data: dict[str, Any]) -> Employee:
    """Parse an Employee from a dictionary."""
    return Employee(
        uid=data.get("uid", ""),
        full_name=data.get("full_name", ""),
        email=data.get("email", ""),
        job_title=data.get("job_title", ""),
        slack_uid=data.get("slack_uid", ""),
        github_id=data.get("github_id", ""),
        rhat_geo=data.get("rhat_geo", ""),
        cost_center=data.get("cost_center", 0),
        manager_uid=data.get("manager_uid", ""),
        is_people_manager=data.get("is_people_manager", False),
    )


def _parse_group_type(data: dict[str, Any] | None) -> GroupType:
    """Parse a GroupType from a dictionary."""
    if not data:
        return GroupType()
    return GroupType(name=data.get("name", ""))


def _parse_channel_info(data: dict[str, Any]) -> ChannelInfo:
    """Parse a ChannelInfo from a dictionary."""
    return ChannelInfo(
        channel=data.get("channel", ""),
        channel_id=data.get("channel_id", ""),
        description=data.get("description", ""),
        types=tuple(data.get("types", [])),
    )


def _parse_alias_info(data: dict[str, Any]) -> AliasInfo:
    """Parse an AliasInfo from a dictionary."""
    return AliasInfo(
        alias=data.get("alias", ""),
        description=data.get("description", ""),
    )


def _parse_slack_config(data: dict[str, Any] | None) -> SlackConfig | None:
    """Parse a SlackConfig from a dictionary."""
    if not data:
        return None
    return SlackConfig(
        channels=tuple(_parse_channel_info(c) for c in data.get("channels", [])),
        aliases=tuple(_parse_alias_info(a) for a in data.get("aliases", [])),
    )


def _parse_role_info(data: dict[str, Any]) -> RoleInfo:
    """Parse a RoleInfo from a dictionary."""
    return RoleInfo(
        people=tuple(data.get("people", [])),
        types=tuple(data.get("types", [])),
    )


def _parse_jira_info(data: dict[str, Any]) -> JiraInfo:
    """Parse a JiraInfo from a dictionary."""
    return JiraInfo(
        project=data.get("project", ""),
        component=data.get("component", ""),
        description=data.get("description", ""),
        view=data.get("view", ""),
        types=tuple(data.get("types", [])),
    )


def _parse_repo_info(data: dict[str, Any]) -> RepoInfo:
    """Parse a RepoInfo from a dictionary."""
    return RepoInfo(
        repo=data.get("repo", ""),
        description=data.get("description", ""),
        tags=tuple(data.get("tags", [])),
        path=data.get("path", ""),
        roles=tuple(data.get("roles", [])),
        branch=data.get("branch", ""),
        types=tuple(data.get("types", [])),
    )


def _parse_email_info(data: dict[str, Any]) -> EmailInfo:
    """Parse an EmailInfo from a dictionary."""
    return EmailInfo(
        address=data.get("address", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
    )


def _parse_resource_info(data: dict[str, Any]) -> ResourceInfo:
    """Parse a ResourceInfo from a dictionary."""
    return ResourceInfo(
        name=data.get("name", ""),
        url=data.get("url", ""),
        description=data.get("description", ""),
    )


def _parse_component_role_info(data: dict[str, Any]) -> ComponentRoleInfo:
    """Parse a ComponentRoleInfo from a dictionary."""
    return ComponentRoleInfo(
        component=data.get("component", ""),
        types=tuple(data.get("types", [])),
    )


def _parse_group(data: dict[str, Any] | None) -> Group:
    """Parse a Group from a dictionary."""
    if not data:
        return Group()
    return Group(
        type=_parse_group_type(data.get("type")),
        resolved_people_uid_list=tuple(data.get("resolved_people_uid_list", [])),
        slack=_parse_slack_config(data.get("slack")),
        roles=tuple(_parse_role_info(r) for r in data.get("roles", [])),
        jiras=tuple(_parse_jira_info(j) for j in data.get("jiras", [])),
        repos=tuple(_parse_repo_info(r) for r in data.get("repos", [])),
        keywords=tuple(data.get("keywords", [])),
        emails=tuple(_parse_email_info(e) for e in data.get("emails", [])),
        resources=tuple(_parse_resource_info(r) for r in data.get("resources", [])),
        component_roles=tuple(
            _parse_component_role_info(c) for c in data.get("component_roles", [])
        ),
    )


def _parse_team(data: dict[str, Any]) -> Team:
    """Parse a Team from a dictionary."""
    return Team(
        uid=data.get("uid", ""),
        name=data.get("name", ""),
        tab_name=data.get("tab_name", ""),
        description=data.get("description", ""),
        type=data.get("type", ""),
        group=_parse_group(data.get("group")),
    )


def _parse_org(data: dict[str, Any]) -> Org:
    """Parse an Org from a dictionary."""
    return Org(
        uid=data.get("uid", ""),
        name=data.get("name", ""),
        tab_name=data.get("tab_name", ""),
        description=data.get("description", ""),
        type=data.get("type", ""),
        group=_parse_group(data.get("group")),
    )


def _parse_pillar(data: dict[str, Any]) -> Pillar:
    """Parse a Pillar from a dictionary."""
    return Pillar(
        uid=data.get("uid", ""),
        name=data.get("name", ""),
        tab_name=data.get("tab_name", ""),
        description=data.get("description", ""),
        type=data.get("type", ""),
        group=_parse_group(data.get("group")),
    )


def _parse_team_group(data: dict[str, Any]) -> TeamGroup:
    """Parse a TeamGroup from a dictionary."""
    return TeamGroup(
        uid=data.get("uid", ""),
        name=data.get("name", ""),
        tab_name=data.get("tab_name", ""),
        description=data.get("description", ""),
        type=data.get("type", ""),
        group=_parse_group(data.get("group")),
    )


def _parse_membership_info(data: dict[str, Any]) -> MembershipInfo:
    """Parse a MembershipInfo from a dictionary."""
    return MembershipInfo(
        name=data.get("name", ""),
        type=data.get("type", ""),
    )


def _parse_ancestry(data: dict[str, Any] | None) -> Ancestry:
    """Parse an Ancestry from a dictionary."""
    if not data:
        return Ancestry()
    return Ancestry(
        orgs=tuple(data.get("orgs", [])),
        teams=tuple(data.get("teams", [])),
        pillars=tuple(data.get("pillars", [])),
        team_groups=tuple(data.get("team_groups", [])),
    )


def _parse_relationship_info(data: dict[str, Any]) -> RelationshipInfo:
    """Parse a RelationshipInfo from a dictionary."""
    return RelationshipInfo(
        ancestry=_parse_ancestry(data.get("ancestry")),
    )


def _parse_data(raw_data: dict[str, Any]) -> Data:
    """Parse the complete Data structure from JSON."""
    # Parse metadata
    metadata_raw = raw_data.get("metadata", {})
    metadata = Metadata(
        generated_at=metadata_raw.get("generated_at", ""),
        data_version=metadata_raw.get("data_version", ""),
        total_employees=metadata_raw.get("total_employees", 0),
        total_orgs=metadata_raw.get("total_orgs", 0),
        total_teams=metadata_raw.get("total_teams", 0),
    )

    # Parse lookups
    lookups_raw = raw_data.get("lookups", {})
    lookups = Lookups(
        employees={k: _parse_employee(v) for k, v in lookups_raw.get("employees", {}).items()},
        teams={k: _parse_team(v) for k, v in lookups_raw.get("teams", {}).items()},
        orgs={k: _parse_org(v) for k, v in lookups_raw.get("orgs", {}).items()},
        pillars={k: _parse_pillar(v) for k, v in lookups_raw.get("pillars", {}).items()},
        team_groups={k: _parse_team_group(v) for k, v in lookups_raw.get("team_groups", {}).items()},
    )

    # Parse indexes
    indexes_raw = raw_data.get("indexes", {})
    membership_raw = indexes_raw.get("membership", {})
    
    # Parse membership index
    membership_index_raw = membership_raw.get("membership_index", {})
    membership_index = {
        k: tuple(_parse_membership_info(m) for m in v)
        for k, v in membership_index_raw.items()
    }
    
    # Parse relationship index
    relationship_index_raw = membership_raw.get("relationship_index", {})
    relationship_index = {}
    for category, items in relationship_index_raw.items():
        relationship_index[category] = {
            k: _parse_relationship_info(v)
            for k, v in items.items()
        }

    membership = MembershipIndex(
        membership_index=membership_index,
        relationship_index=relationship_index,
    )

    slack_mappings_raw = indexes_raw.get("slack_id_mappings", {})
    slack_id_mappings = SlackIDMappings(
        slack_uid_to_uid=slack_mappings_raw.get("slack_uid_to_uid", {}),
    )

    github_mappings_raw = indexes_raw.get("github_id_mappings", {})
    github_id_mappings = GitHubIDMappings(
        github_id_to_uid=github_mappings_raw.get("github_id_to_uid", {}),
    )

    indexes = Indexes(
        membership=membership,
        slack_id_mappings=slack_id_mappings,
        github_id_mappings=github_id_mappings,
    )

    return Data(
        metadata=metadata,
        lookups=lookups,
        indexes=indexes,
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

        # Support constructor injection
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
            logger.error("Failed to load from data source", extra={"source": str(source), "error": str(e)})
            raise DataLoadError(f"failed to load from data source {source}: {e}") from e

        try:
            raw_data = json.load(reader)
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
        """
        logger = get_logger()

        # Perform initial load
        self.load_from_data_source(source)

        # Define callback for reload
        def callback() -> Optional[Exception]:
            try:
                logger.info("Reloading data from source", extra={"source": str(source)})
                self.load_from_data_source(source)
                return None
            except Exception as e:
                logger.error("Failed to reload data", extra={"source": str(source), "error": str(e)})
                return e

        # Start watcher
        logger.info("Starting data source watcher", extra={"source": str(source)})
        err = source.watch(callback)
        if err:
            logger.error("Failed to start watcher", extra={"source": str(source), "error": str(err)})
            raise err

    def is_healthy(self) -> bool:
        """Check if the service is healthy and has data loaded.

        Useful for Kubernetes liveness/readiness probes.

        Returns:
            True if data is loaded and service is operational.

        Example:
            # In a health check endpoint
            @app.get("/healthz")
            def health():
                if not service.is_healthy():
                    return {"status": "unhealthy"}, 503
                return {"status": "healthy"}
        """
        with self._lock:
            return self._data is not None

    def is_ready(self) -> bool:
        """Check if the service is ready to serve requests.

        More thorough than is_healthy - checks that data is loaded
        and contains expected content.

        Returns:
            True if service is ready to serve requests.
        """
        with self._lock:
            if self._data is None:
                return False
            # Verify we have the expected data structures
            return (
                self._data.lookups is not None
                and self._data.indexes is not None
            )

    def get_version(self) -> DataVersion:
        """Get the current data version."""
        with self._lock:
            return self._version

    def get_employee_by_uid(self, uid: str) -> Optional[Employee]:
        """Get an employee by UID."""
        with self._lock:
            if self._data is None or not self._data.lookups.employees:
                return None
            return self._data.lookups.employees.get(uid)

    def get_employee_by_slack_id(self, slack_id: str) -> Optional[Employee]:
        """Get an employee by Slack ID."""
        with self._lock:
            if (
                self._data is None
                or not self._data.indexes.slack_id_mappings.slack_uid_to_uid
                or not self._data.lookups.employees
            ):
                return None

            uid = self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(slack_id, "")
            if not uid:
                return None

            return self._data.lookups.employees.get(uid)

    def get_employee_by_github_id(self, github_id: str) -> Optional[Employee]:
        """Get an employee by GitHub ID."""
        with self._lock:
            if (
                self._data is None
                or not self._data.indexes.github_id_mappings.github_id_to_uid
                or not self._data.lookups.employees
            ):
                return None

            uid = self._data.indexes.github_id_mappings.github_id_to_uid.get(github_id, "")
            if not uid:
                return None

            return self._data.lookups.employees.get(uid)

    def get_manager_for_employee(self, uid: str) -> Optional[Employee]:
        """Get the manager for a given employee UID."""
        with self._lock:
            if self._data is None or not self._data.lookups.employees:
                return None

            # Get the employee first
            emp = self._data.lookups.employees.get(uid)
            if not emp:
                return None

            # Check if employee has a manager
            if not emp.manager_uid:
                return None

            # Look up the manager
            return self._data.lookups.employees.get(emp.manager_uid)

    def get_team_by_name(self, team_name: str) -> Optional[Team]:
        """Get a team by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return None
            return self._data.lookups.teams.get(team_name)

    def get_org_by_name(self, org_name: str) -> Optional[Org]:
        """Get an organization by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.orgs:
                return None
            return self._data.lookups.orgs.get(org_name)

    def get_pillar_by_name(self, pillar_name: str) -> Optional[Pillar]:
        """Get a pillar by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.pillars:
                return None
            return self._data.lookups.pillars.get(pillar_name)

    def get_team_group_by_name(self, team_group_name: str) -> Optional[TeamGroup]:
        """Get a team group by name."""
        with self._lock:
            if self._data is None or not self._data.lookups.team_groups:
                return None
            return self._data.lookups.team_groups.get(team_group_name)

    def get_teams_for_uid(self, uid: str) -> list[str]:
        """Get all teams a UID is a member of."""
        with self._lock:
            if self._data is None or not self._data.indexes.membership.membership_index:
                return []

            memberships = self._data.indexes.membership.membership_index.get(uid, ())
            teams = []
            for membership in memberships:
                if membership.type == MembershipType.TEAM:
                    teams.append(membership.name)
            return teams

    def get_teams_for_slack_id(self, slack_id: str) -> list[str]:
        """Get all teams a Slack user is a member of."""
        uid = self._get_uid_from_slack_id(slack_id)
        if not uid:
            return []
        return self.get_teams_for_uid(uid)

    def get_team_members(self, team_name: str) -> list[Employee]:
        """Get all members of a team."""
        with self._lock:
            if self._data is None or not self._data.lookups.teams:
                return []

            team = self._data.lookups.teams.get(team_name)
            if not team:
                return []

            # Get employee objects for each UID
            members = []
            for uid in team.group.resolved_people_uid_list:
                emp = self._data.lookups.employees.get(uid)
                if emp:
                    members.append(emp)

            return members

    def is_employee_in_team(self, uid: str, team_name: str) -> bool:
        """Check if an employee is in a specific team."""
        teams = self.get_teams_for_uid(uid)
        return team_name in teams

    def is_slack_user_in_team(self, slack_id: str, team_name: str) -> bool:
        """Check if a Slack user is in a specific team."""
        uid = self._get_uid_from_slack_id(slack_id)
        if not uid:
            return False
        return self.is_employee_in_team(uid, team_name)

    def is_employee_in_org(self, uid: str, org_name: str) -> bool:
        """Check if an employee is in a specific organization."""
        with self._lock:
            if self._data is None or not self._data.indexes.membership.membership_index:
                return False

            memberships = self._data.indexes.membership.membership_index.get(uid, ())

            # Get relationship index once
            relationship_index = self._data.indexes.membership.relationship_index
            teams_index = relationship_index.get("teams", {})

            for membership in memberships:
                if membership.type == MembershipType.ORG and membership.name == org_name:
                    return True
                elif membership.type == MembershipType.TEAM:
                    # Check if team belongs to the specified org through relationship index
                    team_relationships = teams_index.get(membership.name)
                    if team_relationships:
                        if org_name in team_relationships.ancestry.orgs:
                            return True

            return False

    def is_slack_user_in_org(self, slack_id: str, org_name: str) -> bool:
        """Check if a Slack user is in a specific organization."""
        uid = self._get_uid_from_slack_id(slack_id)
        if not uid:
            return False
        return self.is_employee_in_org(uid, org_name)

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
            seen_items: set[str] = set()

            # Get relationship index once
            relationship_index = self._data.indexes.membership.relationship_index
            teams_index = relationship_index.get("teams", {})

            for membership in memberships:
                if membership.type == MembershipType.ORG:
                    # Direct organization membership
                    if membership.name not in seen_items:
                        orgs.append(OrgInfo(
                            name=membership.name,
                            type=OrgInfoType.ORGANIZATION,
                        ))
                        seen_items.add(membership.name)
                elif membership.type == MembershipType.TEAM:
                    # Add the team membership itself
                    if membership.name not in seen_items:
                        orgs.append(OrgInfo(
                            name=membership.name,
                            type=OrgInfoType.TEAM,
                        ))
                        seen_items.add(membership.name)

                    # Get team's hierarchy directly from relationship index
                    team_relationships = teams_index.get(membership.name)
                    if team_relationships:
                        # Add all ancestry items
                        self._add_ancestry_items(orgs, seen_items, team_relationships.ancestry)

            return orgs

    def _add_ancestry_items(
        self,
        orgs: list[OrgInfo],
        seen_items: set[str],
        ancestry: Ancestry,
    ) -> None:
        """Add all ancestry items to the orgs list, avoiding duplicates."""
        # Add organizations
        for org_name in ancestry.orgs:
            if org_name not in seen_items:
                orgs.append(OrgInfo(
                    name=org_name,
                    type=OrgInfoType.ORGANIZATION,
                ))
                seen_items.add(org_name)

        # Add pillars
        for pillar_name in ancestry.pillars:
            if pillar_name not in seen_items:
                orgs.append(OrgInfo(
                    name=pillar_name,
                    type=OrgInfoType.PILLAR,
                ))
                seen_items.add(pillar_name)

        # Add team groups
        for team_group_name in ancestry.team_groups:
            if team_group_name not in seen_items:
                orgs.append(OrgInfo(
                    name=team_group_name,
                    type=OrgInfoType.TEAM_GROUP,
                ))
                seen_items.add(team_group_name)

        # Add parent teams
        for parent_team_name in ancestry.teams:
            if parent_team_name not in seen_items:
                orgs.append(OrgInfo(
                    name=parent_team_name,
                    type=OrgInfoType.PARENT_TEAM,
                ))
                seen_items.add(parent_team_name)

    def _get_uid_from_slack_id(self, slack_id: str) -> str:
        """Get the UID for a given Slack ID."""
        if self._data is None or not self._data.indexes.slack_id_mappings.slack_uid_to_uid:
            return ""
        return self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(slack_id, "")

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


