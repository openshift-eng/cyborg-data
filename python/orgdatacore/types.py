"""Type definitions for orgdatacore."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


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
    slack: Optional[SlackConfig] = None
    roles: tuple[RoleInfo, ...] = ()
    jiras: tuple[JiraInfo, ...] = ()
    repos: tuple[RepoInfo, ...] = ()
    keywords: tuple[str, ...] = ()
    emails: tuple[EmailInfo, ...] = ()
    resources: tuple[ResourceInfo, ...] = ()
    component_roles: tuple[ComponentRoleInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class Team:
    """Represents a team in the organizational data."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    group: Group = field(default_factory=Group)


@dataclass(frozen=True, slots=True)
class Org:
    """Represents an organization in the organizational data."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    group: Group = field(default_factory=Group)


@dataclass(frozen=True, slots=True)
class Pillar:
    """Represents a pillar in the organizational hierarchy."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    group: Group = field(default_factory=Group)


@dataclass(frozen=True, slots=True)
class TeamGroup:
    """Represents a team group in the organizational hierarchy."""

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    group: Group = field(default_factory=Group)


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

    employees: dict[str, Employee] = field(default_factory=dict)
    teams: dict[str, Team] = field(default_factory=dict)
    orgs: dict[str, Org] = field(default_factory=dict)
    pillars: dict[str, Pillar] = field(default_factory=dict)
    team_groups: dict[str, TeamGroup] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MembershipInfo:
    """Represents a membership entry with name and type."""

    name: str = ""
    type: str = ""


@dataclass(frozen=True, slots=True)
class Ancestry:
    """Represents ancestry information."""

    orgs: tuple[str, ...] = ()
    teams: tuple[str, ...] = ()
    pillars: tuple[str, ...] = ()
    team_groups: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationshipInfo:
    """Represents relationship information with ancestry."""

    ancestry: Ancestry = field(default_factory=Ancestry)


@dataclass(frozen=True, slots=True)
class MembershipIndex:
    """Represents the membership index structure."""

    membership_index: dict[str, tuple[MembershipInfo, ...]] = field(default_factory=dict)
    relationship_index: dict[str, dict[str, RelationshipInfo]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SlackIDMappings:
    """Contains Slack ID to UID mappings."""

    slack_uid_to_uid: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GitHubIDMappings:
    """Contains GitHub ID to UID mappings."""

    github_id_to_uid: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Indexes:
    """Contains pre-computed lookup tables."""

    membership: MembershipIndex = field(default_factory=MembershipIndex)
    slack_id_mappings: SlackIDMappings = field(default_factory=SlackIDMappings)
    github_id_mappings: GitHubIDMappings = field(default_factory=GitHubIDMappings)


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
    config_maps: dict[str, str] = field(default_factory=dict)
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
