"""
orgdatacore - Python library for organizational data management.

This is a Python port of the Go orgdatacore library, providing thread-safe
access to organizational data including employees, teams, organizations,
pillars, and team groups.

Example with GCS:
    from orgdatacore import Service, GCSConfig, GCSDataSource
    from datetime import timedelta

    config = GCSConfig(
        bucket="your-bucket",
        object_path="path/to/data.json",
        project_id="your-project",
        check_interval=timedelta(minutes=5),
    )
    source = GCSDataSource(config)

    service = Service()
    service.load_from_data_source(source)

Example with custom DataSource:
    class S3DataSource:  # No inheritance needed - duck typing!
        def load(self) -> BinaryIO: ...
        def watch(self, callback) -> Optional[Exception]: ...
        def __str__(self) -> str: ...

    service = Service()
    service.load_from_data_source(S3DataSource("my-bucket", "key"))
"""

from ._anonymization import AnonymizingDataSource, AsyncAnonymizingDataSource
from ._async import AsyncGCSDataSource, AsyncService
from ._exceptions import (
    ConfigurationError,
    DataLoadError,
    DataSourceError,
    GCSError,
    OrgDataError,
)
from ._gcs import GCSDataSource
from ._log import configure_default_logging, get_logger, set_logger
from ._redaction import AsyncRedactingDataSource, RedactingDataSource
from ._service import Service
from ._types import (
    AliasInfo,
    ChannelInfo,
    Component,
    ComponentOwnerInfo,
    ComponentOwnership,
    ComponentOwnershipIndex,
    ContextItemInfo,
    Data,
    DataSource,
    DataVersion,
    EmailInfo,
    Employee,
    EscalationContactInfo,
    GCSConfig,
    GitHubIDMappings,
    Group,
    GroupType,
    HierarchyNode,
    HierarchyPathEntry,
    Indexes,
    JiraIndex,
    JiraInfo,
    JiraOwnerInfo,
    Lookups,
    MembershipIndex,
    MembershipInfo,
    MembershipType,
    Metadata,
    Org,
    OrgInfo,
    OrgInfoType,
    ParentInfo,
    PIIMode,
    Pillar,
    RepoInfo,
    ResourceInfo,
    RoleInfo,
    SlackConfig,
    SlackIDMappings,
    Team,
    TeamGroup,
)
from ._version import (
    API_VERSION,
    __version__,
    __version_info__,
    check_api_compatibility,
    get_version_dict,
)

__all__ = [
    "AnonymizingDataSource",
    "AsyncAnonymizingDataSource",
    "AsyncRedactingDataSource",
    "Employee",
    "Team",
    "Org",
    "Pillar",
    "TeamGroup",
    "Group",
    "GroupType",
    "ParentInfo",
    "Data",
    "Metadata",
    "Lookups",
    "Indexes",
    "MembershipIndex",
    "MembershipInfo",
    "HierarchyPathEntry",
    "HierarchyNode",
    "SlackIDMappings",
    "GitHubIDMappings",
    "JiraIndex",
    "JiraOwnerInfo",
    "SlackConfig",
    "ChannelInfo",
    "AliasInfo",
    "RoleInfo",
    "JiraInfo",
    "RepoInfo",
    "EmailInfo",
    "EscalationContactInfo",
    "ResourceInfo",
    "Component",
    "ComponentOwnerInfo",
    "ComponentOwnership",
    "ComponentOwnershipIndex",
    "ContextItemInfo",
    "OrgInfo",
    "DataVersion",
    "GCSConfig",
    "MembershipType",
    "OrgInfoType",
    "PIIMode",
    "DataSource",
    "RedactingDataSource",
    "Service",
    "AsyncService",
    "GCSDataSource",
    "AsyncGCSDataSource",
    "OrgDataError",
    "DataLoadError",
    "DataSourceError",
    "GCSError",
    "ConfigurationError",
    "get_logger",
    "set_logger",
    "configure_default_logging",
    "__version__",
    "__version_info__",
    "API_VERSION",
    "check_api_compatibility",
    "get_version_dict",
]
