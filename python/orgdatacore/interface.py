"""Interface definitions for orgdatacore.

This module uses Protocol for structural subtyping (duck typing), which matches
Go's interface semantics. Users don't need to inherit from these protocols -
just implement the required methods.

Example custom DataSource:

    class S3DataSource:  # No inheritance needed!
        def load(self) -> BinaryIO:
            ...
        def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
            ...
        def __str__(self) -> str:
            return "s3://bucket/key"
"""

from typing import Protocol, Callable, BinaryIO, Optional, runtime_checkable

from .types import (
    Employee,
    Team,
    Org,
    Pillar,
    TeamGroup,
    OrgInfo,
    DataVersion,
)


@runtime_checkable
class DataSource(Protocol):
    """
    DataSource represents a source of organizational data.

    Implement this protocol to create custom data sources (S3, Azure, etc.).
    No inheritance required - just implement the methods.
    """

    def load(self) -> BinaryIO:
        """
        Returns a file-like object for the organizational data JSON.

        Returns:
            A file-like object containing JSON data.

        Raises:
            Exception: If loading fails.
        """
        ...

    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        """
        Monitors for changes and calls the callback when data is updated.

        Args:
            callback: Function to call when data changes.

        Returns:
            An exception if watching fails, None otherwise.
        """
        ...

    def __str__(self) -> str:
        """Returns a description of this data source."""
        ...


class ServiceInterface(Protocol):
    """
    ServiceInterface defines the core interface for organizational data services.

    This protocol defines all methods that a service implementation must provide.
    """

    # Core data access methods

    def get_employee_by_uid(self, uid: str) -> Optional[Employee]:
        """Get an employee by their UID."""
        ...

    def get_employee_by_slack_id(self, slack_id: str) -> Optional[Employee]:
        """Get an employee by their Slack ID."""
        ...

    def get_employee_by_github_id(self, github_id: str) -> Optional[Employee]:
        """Get an employee by their GitHub ID."""
        ...

    def get_manager_for_employee(self, uid: str) -> Optional[Employee]:
        """Get the manager for a given employee UID."""
        ...

    def get_team_by_name(self, team_name: str) -> Optional[Team]:
        """Get a team by name."""
        ...

    def get_org_by_name(self, org_name: str) -> Optional[Org]:
        """Get an organization by name."""
        ...

    def get_pillar_by_name(self, pillar_name: str) -> Optional[Pillar]:
        """Get a pillar by name."""
        ...

    def get_team_group_by_name(self, team_group_name: str) -> Optional[TeamGroup]:
        """Get a team group by name."""
        ...

    # Membership queries

    def get_teams_for_uid(self, uid: str) -> list[str]:
        """Get all teams a UID is a member of."""
        ...

    def get_teams_for_slack_id(self, slack_id: str) -> list[str]:
        """Get all teams a Slack user is a member of."""
        ...

    def get_team_members(self, team_name: str) -> list[Employee]:
        """Get all members of a team."""
        ...

    def is_employee_in_team(self, uid: str, team_name: str) -> bool:
        """Check if an employee is in a specific team."""
        ...

    def is_slack_user_in_team(self, slack_id: str, team_name: str) -> bool:
        """Check if a Slack user is in a specific team."""
        ...

    # Organization queries

    def is_employee_in_org(self, uid: str, org_name: str) -> bool:
        """Check if an employee is in a specific organization."""
        ...

    def is_slack_user_in_org(self, slack_id: str, org_name: str) -> bool:
        """Check if a Slack user is in a specific organization."""
        ...

    def get_user_organizations(self, slack_user_id: str) -> list[OrgInfo]:
        """Get the complete organizational hierarchy a Slack user belongs to."""
        ...

    # Data management

    def get_version(self) -> DataVersion:
        """Get the current data version."""
        ...

    def load_from_data_source(self, source: DataSource) -> None:
        """
        Load organizational data from a data source.

        Raises:
            Exception: If loading fails.
        """
        ...

    def start_data_source_watcher(self, source: DataSource) -> None:
        """
        Start watching a data source for changes.

        Raises:
            Exception: If starting the watcher fails.
        """
        ...

    # Enumeration methods

    def get_all_employee_uids(self) -> list[str]:
        """Get all employee UIDs in the system."""
        ...

    def get_all_team_names(self) -> list[str]:
        """Get all team names in the system."""
        ...

    def get_all_org_names(self) -> list[str]:
        """Get all organization names in the system."""
        ...

    def get_all_pillar_names(self) -> list[str]:
        """Get all pillar names in the system."""
        ...

    def get_all_team_group_names(self) -> list[str]:
        """Get all team group names in the system."""
        ...
