"""Test helpers for orgdatacore."""

import json
from collections.abc import Callable
from io import BytesIO
from typing import BinaryIO

from orgdatacore._serialization import data_to_dict
from orgdatacore._types import (
    Component,
    Data,
    Employee,
    GitHubIDMappings,
    Group,
    GroupType,
    Indexes,
    JiraIndex,
    JiraOwnerInfo,
    Lookups,
    MembershipIndex,
    MembershipInfo,
    Metadata,
    Org,
    ParentInfo,
    Pillar,
    SlackIDMappings,
    Team,
    TeamGroup,
)


class FakeDataSource:
    """FakeDataSource implements DataSource for testing with controllable data."""

    def __init__(
        self,
        data: str = "",
        load_error: Exception | None = None,
        watch_error: Exception | None = None,
        description: str = "fake-data-source",
    ) -> None:
        """
        Create a fake data source for testing.

        Args:
            data: JSON string data to return from load().
            load_error: Error to raise from load().
            watch_error: Error to return from watch().
            description: Description string for __str__.
        """
        self.data = data
        self.load_error = load_error
        self.watch_error = watch_error
        self.description = description
        self.watch_called = False

    def load(self) -> BinaryIO:
        """Return the test data."""
        if self.load_error:
            raise self.load_error
        return BytesIO(self.data.encode("utf-8"))

    def watch(self, callback: Callable[[], Exception | None]) -> Exception | None:
        """Track that watch was called but don't actually watch."""
        self.watch_called = True
        if self.watch_error:
            return self.watch_error
        return None

    def __str__(self) -> str:
        """Return the description."""
        return self.description


def create_test_data() -> Data:
    """Create comprehensive test data for testing."""
    return Data(
        metadata=Metadata(
            generated_at="2024-01-01T00:00:00Z",
            data_version="test-v1.0",
            total_employees=2,
            total_orgs=1,
            total_teams=1,
        ),
        lookups=Lookups(
            employees={
                "testuser1": Employee(
                    uid="testuser1",
                    full_name="Test User One",
                    email="testuser1@example.com",
                    job_title="Test Engineer",
                    slack_uid="U111111",
                    github_id="ghuser1",
                    manager_uid="testuser2",
                ),
                "testuser2": Employee(
                    uid="testuser2",
                    full_name="Test User Two",
                    email="testuser2@example.com",
                    job_title="Test Manager",
                    slack_uid="U222222",
                    github_id="ghuser2",
                    is_people_manager=True,
                ),
            },
            teams={
                "test-squad": Team(
                    uid="team1",
                    name="test-squad",
                    type="team",
                    parent=ParentInfo(name="test-team-group", type="team_group"),
                    group=Group(
                        type=GroupType(name="team"),
                        resolved_people_uid_list=("testuser1", "testuser2"),
                    ),
                ),
            },
            orgs={
                "test-division": Org(
                    uid="org1",
                    name="test-division",
                    type="organization",
                    group=Group(
                        type=GroupType(name="organization"),
                        resolved_people_uid_list=("testuser1", "testuser2"),
                    ),
                ),
            },
            pillars={
                "test-pillar": Pillar(
                    uid="pillar1",
                    name="test-pillar",
                    type="pillar",
                    parent=ParentInfo(name="test-division", type="org"),
                    group=Group(
                        type=GroupType(name="pillar"),
                        resolved_people_uid_list=("testuser1", "testuser2"),
                    ),
                ),
            },
            team_groups={
                "test-team-group": TeamGroup(
                    uid="tg1",
                    name="test-team-group",
                    type="team_group",
                    parent=ParentInfo(name="test-pillar", type="pillar"),
                    group=Group(
                        type=GroupType(name="team_group"),
                        resolved_people_uid_list=("testuser1", "testuser2"),
                    ),
                ),
            },
            components={
                "test-component": Component(
                    name="test-component",
                    type="system",
                    description="Test component",
                ),
            },
        ),
        indexes=Indexes(
            membership=MembershipIndex(
                membership_index={
                    "testuser1": (
                        MembershipInfo(name="test-squad", type="team"),
                        MembershipInfo(name="test-division", type="org"),
                    ),
                    "testuser2": (
                        MembershipInfo(name="test-squad", type="team"),
                        MembershipInfo(name="test-division", type="org"),
                    ),
                },
            ),
            slack_id_mappings=SlackIDMappings(
                slack_uid_to_uid={
                    "U111111": "testuser1",
                    "U222222": "testuser2",
                },
            ),
            github_id_mappings=GitHubIDMappings(
                github_id_to_uid={
                    "ghuser1": "testuser1",
                    "ghuser2": "testuser2",
                },
            ),
            jira=JiraIndex(
                project_component_owners={
                    "TEST": {
                        "Core": (JiraOwnerInfo(name="test-squad", type="team"),),
                        "_project_level": (
                            JiraOwnerInfo(name="test-squad", type="team"),
                        ),
                    },
                    "PLAT": {
                        "API": (JiraOwnerInfo(name="test-squad", type="team"),),
                    },
                },
            ),
        ),
    )


def create_test_data_json() -> str:
    """Create test data as JSON string."""
    data = create_test_data()
    return json.dumps(data_to_dict(data))
