"""Type definitions and constants for orgdatacore."""

from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, BinaryIO, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PIIMode(StrEnum):
    """Controls PII visibility in organizational data."""

    FULL = "full"
    REDACTED = "redacted"
    ANONYMIZED = "anonymized"


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


class Employee(BaseModel):
    """Represents an employee in the organizational data."""

    model_config = ConfigDict(frozen=True)

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
    timezone: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data: Any) -> Any:
        """Coerce null string fields to empty strings to match Go zero-value semantics."""
        if not isinstance(data, dict):
            return data
        for key in (
            "uid",
            "full_name",
            "email",
            "job_title",
            "slack_uid",
            "github_id",
            "rhat_geo",
            "manager_uid",
            "timezone",
        ):
            if key in data and data[key] is None:
                data[key] = ""
        return data


class ChannelInfo(BaseModel):
    """Represents a Slack channel configuration."""

    model_config = ConfigDict(frozen=True)

    channel: str = ""
    channel_id: str = ""
    description: str = ""
    types: tuple[str, ...] = ()


class AliasInfo(BaseModel):
    """Represents a Slack alias configuration."""

    model_config = ConfigDict(frozen=True)

    alias: str = ""
    description: str = ""


class SlackConfig(BaseModel):
    """Contains Slack channel and alias configuration."""

    model_config = ConfigDict(frozen=True)

    channels: tuple[ChannelInfo, ...] = ()
    aliases: tuple[AliasInfo, ...] = ()


class RoleInfo(BaseModel):
    """Represents a role assignment with associated people."""

    model_config = ConfigDict(frozen=True)

    people: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    description: str = ""


class JiraInfo(BaseModel):
    """Represents Jira project/component configuration."""

    model_config = ConfigDict(frozen=True)

    project: str = ""
    component: str = ""
    description: str = ""
    view: str = ""
    types: tuple[str, ...] = ()


class RepoInfo(BaseModel):
    """Represents GitHub repository configuration."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    repo: str = Field(default="", alias="repo_name")
    description: str = ""
    tags: tuple[str, ...] = ()
    path: str = ""
    roles: tuple[str, ...] = ()
    branch: str = ""
    types: tuple[str, ...] = ()


class EmailInfo(BaseModel):
    """Represents an email configuration."""

    model_config = ConfigDict(frozen=True)

    address: str = ""
    name: str = ""
    description: str = ""


class ResourceInfo(BaseModel):
    """Represents a resource/documentation link."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    url: str = ""
    description: str = ""


class EscalationContactInfo(BaseModel):
    """Represents an escalation contact for incident response."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    url: str = ""
    description: str = ""


class GroupType(BaseModel):
    """Contains group type information."""

    model_config = ConfigDict(frozen=True)

    name: str = ""


class Group(BaseModel):
    """Contains group metadata and configuration."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    type: GroupType = Field(default_factory=GroupType)
    resolved_people_uid_list: tuple[str, ...] = ()
    slack: SlackConfig | None = None
    roles: tuple[RoleInfo, ...] = Field(default=(), alias="resolved_roles")
    jiras: tuple[JiraInfo, ...] = ()
    repos: tuple[RepoInfo, ...] = ()
    keywords: tuple[str, ...] = ()
    emails: tuple[EmailInfo, ...] = ()
    resources: tuple[ResourceInfo, ...] = ()
    escalation: tuple[EscalationContactInfo, ...] = ()
    component_roles: tuple[str, ...] = ()


class ParentInfo(BaseModel):
    """Parent reference for hierarchy traversal."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""


class Team(BaseModel):
    """Represents a team in the organizational data."""

    model_config = ConfigDict(frozen=True)

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = Field(default_factory=Group)


class Org(BaseModel):
    """Represents an organization in the organizational data."""

    model_config = ConfigDict(frozen=True)

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = Field(default_factory=Group)


class Pillar(BaseModel):
    """Represents a pillar in the organizational hierarchy."""

    model_config = ConfigDict(frozen=True)

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = Field(default_factory=Group)


class TeamGroup(BaseModel):
    """Represents a team group in the organizational hierarchy."""

    model_config = ConfigDict(frozen=True)

    uid: str = ""
    name: str = ""
    tab_name: str = ""
    description: str = ""
    type: str = ""
    parent: ParentInfo | None = None
    group: Group = Field(default_factory=Group)


class Component(BaseModel):
    """Represents a component in the organizational data."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""
    description: str = ""
    parent: ParentInfo | None = None
    parent_path: str = ""
    repos: tuple[RepoInfo, ...] = ()
    jiras: tuple[JiraInfo, ...] = ()
    repos_list: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _flatten_nested(cls, data: Any) -> Any:
        """Flatten the nested 'component' key from the indexer format."""
        if not isinstance(data, dict):
            return data
        nested = data.get("component", {})
        if not nested:
            return data
        result = dict(data)
        if not result.get("type"):
            type_val = nested.get("type")
            if isinstance(type_val, dict):
                result["type"] = type_val.get("name", "")
            elif isinstance(type_val, str):
                result["type"] = type_val
        for key in ("repos", "jiras", "repos_list"):
            if not result.get(key):
                result[key] = nested.get(key, [])
        return result


class Metadata(BaseModel):
    """Contains summary information about the data."""

    model_config = ConfigDict(frozen=True)

    generated_at: str = ""
    data_version: str = ""
    total_employees: int = 0
    total_orgs: int = 0
    total_teams: int = 0


class Lookups(BaseModel):
    """Contains the main data objects."""

    model_config = ConfigDict(frozen=True)

    employees: dict[str, Employee] = Field(default_factory=dict)
    teams: dict[str, Team] = Field(default_factory=dict)
    orgs: dict[str, Org] = Field(default_factory=dict)
    pillars: dict[str, Pillar] = Field(default_factory=dict)
    team_groups: dict[str, TeamGroup] = Field(default_factory=dict)
    components: dict[str, Component] = Field(default_factory=dict)


class MembershipInfo(BaseModel):
    """Represents a membership entry with name and type."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""


class HierarchyPathEntry(BaseModel):
    """Single entry in a hierarchy path (name and type)."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""


class MembershipIndex(BaseModel):
    """Represents the membership index structure."""

    model_config = ConfigDict(frozen=True)

    membership_index: dict[str, tuple[MembershipInfo, ...]] = Field(
        default_factory=dict
    )


class SlackIDMappings(BaseModel):
    """Contains Slack ID to UID mappings."""

    model_config = ConfigDict(frozen=True)

    slack_uid_to_uid: dict[str, str] = Field(default_factory=dict)


class GitHubIDMappings(BaseModel):
    """Contains GitHub ID to UID mappings."""

    model_config = ConfigDict(frozen=True)

    github_id_to_uid: dict[str, str] = Field(default_factory=dict)


class HierarchyNode(BaseModel):
    """Node in the descendants tree with nested children."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""
    children: tuple["HierarchyNode", ...] = ()


class ComponentOwnerInfo(BaseModel):
    """Represents an entity that owns a component, with ownership type."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""
    ownership_types: tuple[str, ...] = ()


class ComponentOwnership(BaseModel):
    """Represents a component owned by a team, with ownership type."""

    model_config = ConfigDict(frozen=True)

    component: str = ""
    ownership_types: tuple[str, ...] = ()


class JiraOwnerInfo(BaseModel):
    """Represents an entity that owns a Jira project/component."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""


class JiraIndex(BaseModel):
    """Contains Jira project/component to team mappings.

    Structure: project -> component -> list of owner entities.
    Special key "_project_level" indicates project-level ownership.
    """

    model_config = ConfigDict(frozen=True)

    project_component_owners: dict[str, dict[str, tuple[JiraOwnerInfo, ...]]] = Field(
        default_factory=dict
    )


class ComponentOwnershipIndex(BaseModel):
    """Contains component-to-team ownership mappings.

    Structure: component_name -> list of owner entities with ownership types.
    """

    model_config = ConfigDict(frozen=True)

    component_owners: dict[str, tuple[ComponentOwnerInfo, ...]] = Field(
        default_factory=dict
    )


class Indexes(BaseModel):
    """Contains pre-computed lookup tables."""

    model_config = ConfigDict(frozen=True)

    membership: MembershipIndex = Field(default_factory=MembershipIndex)
    slack_id_mappings: SlackIDMappings = Field(default_factory=SlackIDMappings)
    github_id_mappings: GitHubIDMappings = Field(default_factory=GitHubIDMappings)
    jira: JiraIndex = Field(default_factory=JiraIndex)
    component_ownership: ComponentOwnershipIndex = Field(
        default_factory=ComponentOwnershipIndex
    )


class Data(BaseModel):
    """Represents the comprehensive organizational data structure."""

    model_config = ConfigDict(frozen=True)

    metadata: Metadata = Field(default_factory=Metadata)
    lookups: Lookups = Field(default_factory=Lookups)
    indexes: Indexes = Field(default_factory=Indexes)


class OrgInfo(BaseModel):
    """Represents organization information for a user."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""


class DataVersion(BaseModel):
    """Tracks the version of loaded data for hot reload."""

    model_config = ConfigDict(frozen=True)

    load_time: datetime = Field(default_factory=lambda: datetime.min)
    config_maps: dict[str, str] = Field(default_factory=dict)
    org_count: int = 0
    employee_count: int = 0


class GCSConfig(BaseModel):
    """Represents Google Cloud Storage configuration for data loading."""

    model_config = ConfigDict(frozen=True)

    bucket: str = ""
    object_path: str = ""
    project_id: str = ""
    credentials_json: str = ""
    check_interval: timedelta = Field(default_factory=lambda: timedelta(minutes=5))
