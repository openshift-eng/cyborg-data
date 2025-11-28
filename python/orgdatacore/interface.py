"""Interface definitions for orgdatacore."""

from abc import ABC, abstractmethod
from typing import Callable, BinaryIO, Optional

from .types import (
    Employee,
    Team,
    Org,
    Pillar,
    TeamGroup,
    OrgInfo,
    DataVersion,
)


class DataSource(ABC):
    """DataSource represents a source of organizational data."""

    @abstractmethod
    def load(self) -> BinaryIO:
        """
        Returns a file-like object for the organizational data JSON.

        Returns:
            A file-like object containing JSON data.

        Raises:
            Exception: If loading fails.
        """
        pass

    @abstractmethod
    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        """
        Monitors for changes and calls the callback when data is updated.

        Args:
            callback: Function to call when data changes.

        Returns:
            An exception if watching fails, None otherwise.
        """
        pass

    @abstractmethod
    def __str__(self) -> str:
        """Returns a description of this data source."""
        pass


class ServiceInterface(ABC):
    """ServiceInterface defines the core interface for organizational data services."""

    # Core data access methods

    @abstractmethod
    def get_employee_by_uid(self, uid: str) -> Optional[Employee]:
        """Get an employee by their UID."""
        pass

    @abstractmethod
    def get_employee_by_slack_id(self, slack_id: str) -> Optional[Employee]:
        """Get an employee by their Slack ID."""
        pass

    @abstractmethod
    def get_employee_by_github_id(self, github_id: str) -> Optional[Employee]:
        """Get an employee by their GitHub ID."""
        pass

    @abstractmethod
    def get_manager_for_employee(self, uid: str) -> Optional[Employee]:
        """Get the manager for a given employee UID."""
        pass

    @abstractmethod
    def get_team_by_name(self, team_name: str) -> Optional[Team]:
        """Get a team by name."""
        pass

    @abstractmethod
    def get_org_by_name(self, org_name: str) -> Optional[Org]:
        """Get an organization by name."""
        pass

    @abstractmethod
    def get_pillar_by_name(self, pillar_name: str) -> Optional[Pillar]:
        """Get a pillar by name."""
        pass

    @abstractmethod
    def get_team_group_by_name(self, team_group_name: str) -> Optional[TeamGroup]:
        """Get a team group by name."""
        pass

    # Membership queries

    @abstractmethod
    def get_teams_for_uid(self, uid: str) -> list[str]:
        """Get all teams a UID is a member of."""
        pass

    @abstractmethod
    def get_teams_for_slack_id(self, slack_id: str) -> list[str]:
        """Get all teams a Slack user is a member of."""
        pass

    @abstractmethod
    def get_team_members(self, team_name: str) -> list[Employee]:
        """Get all members of a team."""
        pass

    @abstractmethod
    def is_employee_in_team(self, uid: str, team_name: str) -> bool:
        """Check if an employee is in a specific team."""
        pass

    @abstractmethod
    def is_slack_user_in_team(self, slack_id: str, team_name: str) -> bool:
        """Check if a Slack user is in a specific team."""
        pass

    # Organization queries

    @abstractmethod
    def is_employee_in_org(self, uid: str, org_name: str) -> bool:
        """Check if an employee is in a specific organization."""
        pass

    @abstractmethod
    def is_slack_user_in_org(self, slack_id: str, org_name: str) -> bool:
        """Check if a Slack user is in a specific organization."""
        pass

    @abstractmethod
    def get_user_organizations(self, slack_user_id: str) -> list[OrgInfo]:
        """Get the complete organizational hierarchy a Slack user belongs to."""
        pass

    # Data management

    @abstractmethod
    def get_version(self) -> DataVersion:
        """Get the current data version."""
        pass

    @abstractmethod
    def load_from_data_source(self, source: DataSource) -> None:
        """
        Load organizational data from a data source.

        Raises:
            Exception: If loading fails.
        """
        pass

    @abstractmethod
    def start_data_source_watcher(self, source: DataSource) -> None:
        """
        Start watching a data source for changes.

        Raises:
            Exception: If starting the watcher fails.
        """
        pass

    # Enumeration methods

    @abstractmethod
    def get_all_employee_uids(self) -> list[str]:
        """Get all employee UIDs in the system."""
        pass

    @abstractmethod
    def get_all_team_names(self) -> list[str]:
        """Get all team names in the system."""
        pass

    @abstractmethod
    def get_all_org_names(self) -> list[str]:
        """Get all organization names in the system."""
        pass

    @abstractmethod
    def get_all_pillar_names(self) -> list[str]:
        """Get all pillar names in the system."""
        pass

    @abstractmethod
    def get_all_team_group_names(self) -> list[str]:
        """Get all team group names in the system."""
        pass

