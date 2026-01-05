"""Type definitions and constants for orgdatacore."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import BinaryIO, Protocol


class MembershipType(StrEnum):
    """Membership types for organizational hierarchy."""

    TEAM = "team"
    ORG = "org"


class OrgInfoType(StrEnum):
    """Organization info types returned by get_user_organizations."""

    ORGANIZATION = "Organization"
    TEAM = "Team"
    PILLAR = "Pillar"
    TEAM_GROUP = "Team Group"
    PARENT_TEAM = "Parent Team"


class DataSource(Protocol):
    """
    DataSource represents a source of organizational data.

    Implement this protocol to create custom data sources (S3, Azure, etc.).
    No inheritance required - just implement the methods (duck typing).

    Example:
        class S3DataSource:  # No inheritance needed!
            def load(self) -> BinaryIO:
                ...
            def watch(self, callback) -> Optional[Exception]:
                ...
            def __str__(self) -> str:
                return "s3://bucket/key"
    """

    def load(self) -> BinaryIO:
        """Returns a file-like object for the organizational data JSON."""
        ...

    def watch(self, callback: Callable[[], Exception | None]) -> Exception | None:
        """Monitors for changes and calls the callback when data is updated."""
        ...

    def __str__(self) -> str:
        """Returns a description of this data source."""
        ...


@dataclass(frozen=True, slots=True)
class Employee:
    """Represents an employee in the organizational data."""

    uid: str = ""
    full_name: str = ""
    email: str = ""
    job_title: str = ""
    slack_uid: str = ""
    github_id: str = ""
    rhat_geo: str = ""
    cost_center: int = 0
    manager_uid: str = ""
    is_people_manager: bool = False


@dataclass(frozen=True, slots=True)
class ChannelInfo:
    """Represents a Slack channel configuration."""

    channel: str = ""
    channel_id: str = ""
    description: str = ""
    types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AliasInfo:
    """Represents a Slack alias configuration."""

    alias: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class SlackConfig:
    """Contains Slack channel and alias configuration."""

    channels: tuple[ChannelInfo, ...] = ()
    aliases: tuple[AliasInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class RoleInfo:
    """Represents a role assignment with associated people."""

    people: tuple[str, ...] = ()
    types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class JiraInfo:
    """Represents Jira project/component configuration."""

    project: str = ""
    component: str = ""
    description: str = ""
    view: str = ""
    types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepoInfo:
    """Represents GitHub repository configuration."""

    repo: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    path: str = ""
    roles: tuple[str, ...] = ()
    branch: str = ""
    types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EmailInfo:
    """Represents an email configuration."""

    address: str = ""
    name: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class ResourceInfo:
    """Represents a resource/documentation link."""

    name: str = ""
    url: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class ComponentRoleInfo:
    """Represents component ownership information."""

    component: str = ""
    types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GroupType:
    """Contains group type information."""

    name: str = ""


@dataclass(frozen=True, slots=True)
class Group:
    """Contains group metadata and configuration."""

    type: GroupType = field(default_factory=GroupType)
    resolved_people_uid_list: tuple[str, ...] = ()
    slack: SlackConfig | None = None
    roles: tuple[RoleInfo, ...] = ()
    jiras: tuple[JiraInfo, ...] = ()
    repos: tuple[RepoInfo, ...] = ()
    keywords: tuple[str, ...] = ()
    emails: tuple[EmailInfo, ...] = ()
    resources: tuple[ResourceInfo, ...] = ()
    component_roles: tuple[ComponentRoleInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class ParentInfo:
    """Parent reference for hierarchy traversal."""

    name: str = ""
    type: str = ""


@dataclass(frozen=True, slots=True)
class Team:
    """Represents a team in the organizational data."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = field(default_factory=Group)


@dataclass(frozen=True, slots=True)
class Org:
    """Represents an organization in the organizational data."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = field(default_factory=Group)


@dataclass(frozen=True, slots=True)
class Pillar:
    """Represents a pillar in the organizational hierarchy."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = field(default_factory=Group)


@dataclass(frozen=True, slots=True)
class TeamGroup:
    """Represents a team group in the organizational hierarchy."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = field(default_factory=Group)


@dataclass(frozen=True, slots=True)
class Component:
    """Represents a component in the organizational data."""

    name: str = ""
    type: str = ""
    description: str = ""
    parent: ParentInfo | None = None
    parent_path: str = ""
    repos: tuple[RepoInfo, ...] = ()
    jiras: tuple[JiraInfo, ...] = ()
    repos_list: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Metadata:
    """Contains summary information about the data."""

    generated_at: str = ""
    data_version: str = ""
    total_employees: int = 0
    total_orgs: int = 0
    total_teams: int = 0


@dataclass(frozen=True, slots=True)
class Lookups:
    """Contains the main data objects."""

    employees: dict[str, Employee] = field(default_factory=lambda: {})
    teams: dict[str, Team] = field(default_factory=lambda: {})
    orgs: dict[str, Org] = field(default_factory=lambda: {})
    pillars: dict[str, Pillar] = field(default_factory=lambda: {})
    team_groups: dict[str, TeamGroup] = field(default_factory=lambda: {})
    components: dict[str, Component] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class MembershipInfo:
    """Represents a membership entry with name and type."""

    name: str = ""
    type: str = ""


@dataclass(frozen=True, slots=True)
class HierarchyPathEntry:
    """Single entry in a hierarchy path (name and type)."""

    name: str = ""
    type: str = ""


@dataclass(frozen=True, slots=True)
class MembershipIndex:
    """Represents the membership index structure."""

    membership_index: dict[str, tuple[MembershipInfo, ...]] = field(
        default_factory=lambda: {}
    )


@dataclass(frozen=True, slots=True)
class SlackIDMappings:
    """Contains Slack ID to UID mappings."""

    slack_uid_to_uid: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class GitHubIDMappings:
    """Contains GitHub ID to UID mappings."""

    github_id_to_uid: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    """Node in the descendants tree with nested children."""

    name: str = ""
    type: str = ""
    children: tuple["HierarchyNode", ...] = ()


@dataclass(frozen=True, slots=True)
class JiraOwnerInfo:
    """Represents an entity that owns a Jira project/component."""

    name: str = ""
    type: str = ""


@dataclass(frozen=True, slots=True)
class JiraIndex:
    """Contains Jira project/component to team mappings.

    Structure: project -> component -> list of owner entities.
    Special key "_project_level" indicates project-level ownership.
    """

    project_component_owners: dict[str, dict[str, tuple[JiraOwnerInfo, ...]]] = field(
        default_factory=lambda: {}
    )


@dataclass(frozen=True, slots=True)
class Indexes:
    """Contains pre-computed lookup tables."""

    membership: MembershipIndex = field(default_factory=MembershipIndex)
    slack_id_mappings: SlackIDMappings = field(default_factory=SlackIDMappings)
    github_id_mappings: GitHubIDMappings = field(default_factory=GitHubIDMappings)
    jira: JiraIndex = field(default_factory=JiraIndex)


@dataclass(frozen=True, slots=True)
class Data:
    """Represents the comprehensive organizational data structure."""

    metadata: Metadata = field(default_factory=Metadata)
    lookups: Lookups = field(default_factory=Lookups)
    indexes: Indexes = field(default_factory=Indexes)


@dataclass(frozen=True, slots=True)
class OrgInfo:
    """Represents organization information for a user."""

    name: str = ""
    type: str = ""


@dataclass(frozen=True, slots=True)
class DataVersion:
    """Tracks the version of loaded data for hot reload."""

    load_time: datetime = field(default_factory=lambda: datetime.min)
    config_maps: dict[str, str] = field(default_factory=lambda: {})
    org_count: int = 0
    employee_count: int = 0


@dataclass(frozen=True, slots=True)
class GCSConfig:
    """Represents Google Cloud Storage configuration for data loading."""

    bucket: str = ""
    object_path: str = ""
    project_id: str = ""
    credentials_json: str = ""
    check_interval: timedelta = field(default_factory=lambda: timedelta(minutes=5))
