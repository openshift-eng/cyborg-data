"""Type definitions and constants for orgdatacore.

The on-disk *comprehensive index* models (metadata, lookups, entities, indexes,
and all their nested leaf types) are the canonical ``orgindex-schema`` models,
re-exported here under the historical ``orgdatacore`` names. The
five hierarchy collections (teams/orgs/pillars/team_groups/cohorts) are
structurally identical, so ``Team``/``Org``/``Pillar``/``TeamGroup`` all alias
the single canonical :class:`HierarchyEntity`.

Only the query-result types (``HierarchyPathEntry``, ``HierarchyNode``,
``OrgInfo``, ``ComponentOwnership``) and infrastructure types (``DataVersion``,
``GCSConfig``, ``DataSource``) are defined locally — they are not part of the
on-disk index contract.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import BinaryIO, Protocol

from orgindex_schema import (
    ComponentEntry as Component,
)
from orgindex_schema import (
    ComponentOwner as ComponentOwnerInfo,
)
from orgindex_schema import (
    ComprehensiveIndexModel as Data,
)
from orgindex_schema import (
    ContextItemInfo,
    EmailInfo,
    EscalationContactInfo,
    HierarchyEntity,
    Indexes,
    JiraInfo,
    Lookups,
    Metadata,
    RepoInfo,
    ResourceInfo,
    RoleInfo,
)
from orgindex_schema import (
    EmployeeEntry as Employee,
)
from orgindex_schema import (
    GitHubIdMappings as GitHubIDMappings,
)
from orgindex_schema import (
    GroupInfo as Group,
)
from orgindex_schema import (
    GroupTypeInfo as GroupType,
)
from orgindex_schema import (
    HierarchyEntity as Cohort,
)
from orgindex_schema import (
    HierarchyEntity as Org,
)
from orgindex_schema import (
    HierarchyEntity as Pillar,
)
from orgindex_schema import (
    HierarchyEntity as Team,
)
from orgindex_schema import (
    HierarchyEntity as TeamGroup,
)
from orgindex_schema import (
    JiraOwner as JiraOwnerInfo,
)
from orgindex_schema import (
    MembershipEntry as MembershipInfo,
)
from orgindex_schema import (
    MembershipIndexInfo as MembershipIndex,
)
from orgindex_schema import (
    ParentRef as ParentInfo,
)
from orgindex_schema import (
    SlackAliasInfo as AliasInfo,
)
from orgindex_schema import (
    SlackChannelInfo as ChannelInfo,
)
from orgindex_schema import (
    SlackConfigInfo as SlackConfig,
)
from orgindex_schema import (
    SlackIdMappings as SlackIDMappings,
)
from pydantic import BaseModel, ConfigDict, Field


class MembershipType(StrEnum):
    """Membership types for organizational hierarchy."""

    TEAM = "team"
    ORG = "org"


class EntityType(StrEnum):
    """Hierarchy entity types (matches the Go EntityType enum)."""

    EMPLOYEE = "employee"
    TEAM = "team"
    ORG = "org"
    PILLAR = "pillar"
    TEAM_GROUP = "team_group"


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


class HierarchyPathEntry(BaseModel):
    """Single entry in a hierarchy path (name and type). Query result, not on-disk."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""
    stable_id: str = ""


class HierarchyNode(BaseModel):
    """Node in the descendants tree with nested children. Query result, not on-disk."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""
    stable_id: str = ""
    children: tuple["HierarchyNode", ...] = ()


class ComponentOwnership(BaseModel):
    """A component owned by a team, with ownership type. Query result, not on-disk."""

    model_config = ConfigDict(frozen=True)

    component: str = ""
    ownership_types: tuple[str, ...] = ()


class OrgInfo(BaseModel):
    """Organization information for a user. Query result, not on-disk."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    type: str = ""
    stable_id: str = ""


class DataVersion(BaseModel):
    """Tracks the version of loaded data for hot reload. Infrastructure, not on-disk."""

    model_config = ConfigDict(frozen=True)

    load_time: datetime = Field(default_factory=lambda: datetime.min)
    config_maps: dict[str, str] = Field(default_factory=dict)
    org_count: int = 0
    employee_count: int = 0


class GCSConfig(BaseModel):
    """Google Cloud Storage configuration for data loading. Infrastructure, not on-disk."""

    model_config = ConfigDict(frozen=True)

    bucket: str = ""
    object_path: str = ""
    project_id: str = ""
    credentials_json: str = ""
    check_interval: timedelta = Field(default_factory=lambda: timedelta(minutes=5))


__all__ = [
    # Canonical on-disk index models, re-exported from orgindex-schema under the
    # historical orgdatacore names. Team/Org/Pillar/TeamGroup/Cohort all
    # alias the single canonical HierarchyEntity.
    "Data",
    "Lookups",
    "Indexes",
    "Metadata",
    "Employee",
    "Team",
    "Org",
    "Pillar",
    "TeamGroup",
    "Cohort",
    "HierarchyEntity",
    "Component",
    "Group",
    "GroupType",
    "ParentInfo",
    "ChannelInfo",
    "AliasInfo",
    "SlackConfig",
    "RoleInfo",
    "JiraInfo",
    "RepoInfo",
    "EmailInfo",
    "ResourceInfo",
    "EscalationContactInfo",
    "ContextItemInfo",
    "MembershipInfo",
    "MembershipIndex",
    "SlackIDMappings",
    "GitHubIDMappings",
    "JiraOwnerInfo",
    "ComponentOwnerInfo",
    # Query-result and infrastructure types (not on-disk; stay local).
    "HierarchyPathEntry",
    "HierarchyNode",
    "ComponentOwnership",
    "OrgInfo",
    "DataVersion",
    "GCSConfig",
    "DataSource",
    # Enums.
    "MembershipType",
    "EntityType",
    "OrgInfoType",
]
