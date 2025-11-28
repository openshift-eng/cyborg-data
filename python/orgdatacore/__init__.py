"""
orgdatacore - Python library for organizational data management.

This is a Python port of the Go orgdatacore library, providing thread-safe
access to organizational data including employees, teams, organizations,
pillars, and team groups.

## Data Sources

The only supported production data source is GCS (Google Cloud Storage).
For custom storage backends (S3, Azure, etc.), implement the DataSource interface.

Example with GCS:

    from orgdatacore import Service, GCSConfig
    from orgdatacore.datasources import GCSDataSourceWithSDK
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

    from orgdatacore import Service
    from orgdatacore.interface import DataSource
    from typing import BinaryIO, Callable, Optional
    from io import BytesIO

    class S3DataSource(DataSource):
        def __init__(self, bucket: str, key: str):
            self.bucket = bucket
            self.key = key

        def load(self) -> BinaryIO:
            import boto3
            s3 = boto3.client('s3')
            response = s3.get_object(Bucket=self.bucket, Key=self.key)
            return BytesIO(response['Body'].read())

        def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
            return None  # Implement as needed

        def __str__(self) -> str:
            return f"s3://{self.bucket}/{self.key}"

    service = Service()
    service.load_from_data_source(S3DataSource("my-bucket", "org-data.json"))

NOTE: File-based data sources are NOT supported for production use.
They are only available internally for testing purposes.
"""

from .types import (
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

from .constants import (
    MembershipType,
    OrgInfoType,
    # Legacy constants for backwards compatibility
    MEMBERSHIP_TYPE_TEAM,
    MEMBERSHIP_TYPE_ORG,
    ORG_INFO_TYPE_ORGANIZATION,
    ORG_INFO_TYPE_TEAM,
    ORG_INFO_TYPE_PILLAR,
    ORG_INFO_TYPE_TEAM_GROUP,
    ORG_INFO_TYPE_PARENT_TEAM,
)

from .interface import DataSource, ServiceInterface

from .service import Service

from .datasources import GCSDataSource

from .exceptions import (
    OrgDataError,
    DataLoadError,
    DataSourceError,
    GCSError,
    ConfigurationError,
)

from .logging import get_logger, set_logger, configure_default_logging

from .version import (
    __version__,
    __version_info__,
    API_VERSION,
    check_api_compatibility,
    get_version_dict,
)

from .async_service import AsyncService

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
    # Enums (modern)
    "MembershipType",
    "OrgInfoType",
    # Constants (legacy, for backwards compatibility)
    "MEMBERSHIP_TYPE_TEAM",
    "MEMBERSHIP_TYPE_ORG",
    "ORG_INFO_TYPE_ORGANIZATION",
    "ORG_INFO_TYPE_TEAM",
    "ORG_INFO_TYPE_PILLAR",
    "ORG_INFO_TYPE_TEAM_GROUP",
    "ORG_INFO_TYPE_PARENT_TEAM",
    # Interfaces - Implement DataSource for custom storage backends
    "DataSource",
    "ServiceInterface",
    # Service
    "Service",
    # Data Sources - GCS is the only supported production data source
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
    # Async
    "AsyncService",
]
