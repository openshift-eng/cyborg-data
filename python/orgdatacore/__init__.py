"""
orgdatacore - Python library for organizational data management.

This is a Python port of the Go orgdatacore library, providing thread-safe
access to organizational data including employees, teams, organizations,
pillars, and team groups.

Example with GCS:
    from orgdatacore import Service, GCSConfig, GCSDataSourceWithSDK
    from datetime import timedelta

    config = GCSConfig(
        bucket="your-bucket",
        object_path="path/to/data.json",
        project_id="your-project",
        check_interval=timedelta(minutes=5),
    )
    source = GCSDataSourceWithSDK(config)

    service = Service()
    service.load_from_data_source(source)

Example with custom DataSource:
    class S3DataSource:  # No inheritance needed - duck typing!
        def load(self) -> BinaryIO: ...
        def watch(self, callback) -> Optional[Exception]: ...
        def __str__(self) -> str: ...

    service = Service()
    service.load_from_data_source(S3DataSource("my-bucket", "key"))

NOTE: File-based data sources are NOT supported for production use.
They are only available internally for testing purposes.
"""

# Types and constants
from ._types import (
    # Enums
    MembershipType,
    OrgInfoType,
    # Legacy constants
    MEMBERSHIP_TYPE_TEAM,
    MEMBERSHIP_TYPE_ORG,
    ORG_INFO_TYPE_ORGANIZATION,
    ORG_INFO_TYPE_TEAM,
    ORG_INFO_TYPE_PILLAR,
    ORG_INFO_TYPE_TEAM_GROUP,
    ORG_INFO_TYPE_PARENT_TEAM,
    # Protocol
    DataSource,
    # Data types
    Employee,
    Team,
    Org,
    Pillar,
    TeamGroup,
    Group,
    GroupType,
    Data,
    Metadata,
    Lookups,
    Indexes,
    MembershipIndex,
    MembershipInfo,
    RelationshipInfo,
    Ancestry,
    SlackIDMappings,
    GitHubIDMappings,
    SlackConfig,
    ChannelInfo,
    AliasInfo,
    RoleInfo,
    JiraInfo,
    RepoInfo,
    EmailInfo,
    ResourceInfo,
    ComponentRoleInfo,
    OrgInfo,
    DataVersion,
    GCSConfig,
)

# Exceptions
from ._exceptions import (
    OrgDataError,
    DataLoadError,
    DataSourceError,
    GCSError,
    ConfigurationError,
)

# Logging
from ._log import get_logger, set_logger, configure_default_logging

# Version
from ._version import (
    __version__,
    __version_info__,
    API_VERSION,
    check_api_compatibility,
    get_version_dict,
)

# Service
from ._service import Service

# Async
from ._async import AsyncService

# GCS Data Sources
from ._gcs import GCSDataSource

# Optional: GCSDataSourceWithSDK (requires google-cloud-storage)
try:
    from ._gcs import GCSDataSourceWithSDK
except ImportError:
    pass

# Optional: AsyncGCSDataSource (requires google-cloud-storage)
try:
    from ._async import AsyncGCSDataSource
except ImportError:
    pass

__all__ = [
    # Types
    "Employee",
    "Team",
    "Org",
    "Pillar",
    "TeamGroup",
    "Group",
    "GroupType",
    "Data",
    "Metadata",
    "Lookups",
    "Indexes",
    "MembershipIndex",
    "MembershipInfo",
    "RelationshipInfo",
    "Ancestry",
    "SlackIDMappings",
    "GitHubIDMappings",
    "SlackConfig",
    "ChannelInfo",
    "AliasInfo",
    "RoleInfo",
    "JiraInfo",
    "RepoInfo",
    "EmailInfo",
    "ResourceInfo",
    "ComponentRoleInfo",
    "OrgInfo",
    "DataVersion",
    "GCSConfig",
    # Enums
    "MembershipType",
    "OrgInfoType",
    # Legacy constants
    "MEMBERSHIP_TYPE_TEAM",
    "MEMBERSHIP_TYPE_ORG",
    "ORG_INFO_TYPE_ORGANIZATION",
    "ORG_INFO_TYPE_TEAM",
    "ORG_INFO_TYPE_PILLAR",
    "ORG_INFO_TYPE_TEAM_GROUP",
    "ORG_INFO_TYPE_PARENT_TEAM",
    # Protocol
    "DataSource",
    # Service
    "Service",
    "AsyncService",
    # Data Sources
    "GCSDataSource",
    # Exceptions
    "OrgDataError",
    "DataLoadError",
    "DataSourceError",
    "GCSError",
    "ConfigurationError",
    # Logging
    "get_logger",
    "set_logger",
    "configure_default_logging",
    # Version
    "__version__",
    "__version_info__",
    "API_VERSION",
    "check_api_compatibility",
    "get_version_dict",
]
