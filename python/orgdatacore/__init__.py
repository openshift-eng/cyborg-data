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

from ._types import (
    MembershipType,
    OrgInfoType,
    DataSource,
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

from ._exceptions import (
    OrgDataError,
    DataLoadError,
    DataSourceError,
    GCSError,
    ConfigurationError,
)

from ._log import get_logger, set_logger, configure_default_logging

from ._version import (
    __version__,
    __version_info__,
    API_VERSION,
    check_api_compatibility,
    get_version_dict,
)

from ._service import Service
from ._async import AsyncService
from ._gcs import GCSDataSource

try:
    from ._gcs import GCSDataSourceWithSDK
    from ._async import AsyncGCSDataSource
except ImportError:
    GCSDataSourceWithSDK = None  # type: ignore[misc, assignment]
    AsyncGCSDataSource = None  # type: ignore[misc, assignment]

__all__ = [
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
    "MembershipType",
    "OrgInfoType",
    "DataSource",
    "Service",
    "AsyncService",
    "GCSDataSource",
    "GCSDataSourceWithSDK",
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
