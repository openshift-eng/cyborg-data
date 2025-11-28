"""Test helpers for orgdatacore."""

import json
from io import BytesIO
from typing import BinaryIO, Callable, Optional

from .interface import DataSource
from .types import (
    Data,
    Metadata,
    Lookups,
    Indexes,
    Employee,
    Team,
    Org,
    Group,
    GroupType,
    MembershipIndex,
    MembershipInfo,
    RelationshipInfo,
    Ancestry,
    SlackIDMappings,
    GitHubIDMappings,
)


class FakeDataSource(DataSource):
    """FakeDataSource implements DataSource for testing with controllable data."""

    def __init__(
        self,
        data: str = "",
        load_error: Optional[Exception] = None,
        watch_error: Optional[Exception] = None,
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

    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        """Track that watch was called but don't actually watch."""
        self.watch_called = True
        if self.watch_error:
            return self.watch_error
        return None

    def __str__(self) -> str:
        """Return the description."""
        return self.description


def create_test_data() -> Data:
    """Create minimal valid test data for testing."""
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
                ),
                "testuser2": Employee(
                    uid="testuser2",
                    full_name="Test User Two",
                    email="testuser2@example.com",
                    job_title="Test Manager",
                    slack_uid="U222222",
                ),
            },
            teams={
                "test-squad": Team(
                    uid="team1",
                    name="test-squad",
                    type="team",
                    group=Group(
                        type=GroupType(name="team"),
                        resolved_people_uid_list=["testuser1", "testuser2"],
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
                        resolved_people_uid_list=["testuser1", "testuser2"],
                    ),
                ),
            },
        ),
        indexes=Indexes(
            membership=MembershipIndex(
                membership_index={
                    "testuser1": [
                        MembershipInfo(name="test-squad", type="team"),
                        MembershipInfo(name="test-division", type="org"),
                    ],
                    "testuser2": [
                        MembershipInfo(name="test-squad", type="team"),
                        MembershipInfo(name="test-division", type="org"),
                    ],
                },
                relationship_index={
                    "teams": {
                        "test-squad": RelationshipInfo(
                            ancestry=Ancestry(
                                orgs=["test-division"],
                                teams=[],
                                pillars=[],
                                team_groups=[],
                            ),
                        ),
                    },
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
        ),
    )


def create_test_data_json() -> str:
    """Create test data as JSON string."""
    data = create_test_data()
    return _data_to_json(data)


def create_empty_test_data() -> str:
    """Create test data with no employees/teams/orgs."""
    data = Data(
        metadata=Metadata(
            generated_at="2024-01-01T00:00:00Z",
            data_version="empty-v1.0",
            total_employees=0,
            total_orgs=0,
            total_teams=0,
        ),
        lookups=Lookups(
            employees={},
            teams={},
            orgs={},
        ),
        indexes=Indexes(
            membership=MembershipIndex(
                membership_index={},
                relationship_index={},
            ),
            slack_id_mappings=SlackIDMappings(
                slack_uid_to_uid={},
            ),
            github_id_mappings=GitHubIDMappings(
                github_id_to_uid={},
            ),
        ),
    )
    return _data_to_json(data)


def _data_to_json(data: Data) -> str:
    """Convert Data to JSON string."""
    return json.dumps(_data_to_dict(data))


def _data_to_dict(data: Data) -> dict:
    """Convert Data to dictionary for JSON serialization."""
    return {
        "metadata": {
            "generated_at": data.metadata.generated_at,
            "data_version": data.metadata.data_version,
            "total_employees": data.metadata.total_employees,
            "total_orgs": data.metadata.total_orgs,
            "total_teams": data.metadata.total_teams,
        },
        "lookups": {
            "employees": {
                k: _employee_to_dict(v) for k, v in data.lookups.employees.items()
            },
            "teams": {k: _team_to_dict(v) for k, v in data.lookups.teams.items()},
            "orgs": {k: _org_to_dict(v) for k, v in data.lookups.orgs.items()},
            "pillars": {k: _pillar_to_dict(v) for k, v in data.lookups.pillars.items()},
            "team_groups": {
                k: _team_group_to_dict(v) for k, v in data.lookups.team_groups.items()
            },
        },
        "indexes": {
            "membership": {
                "membership_index": {
                    k: [{"name": m.name, "type": m.type} for m in v]
                    for k, v in data.indexes.membership.membership_index.items()
                },
                "relationship_index": {
                    cat: {
                        k: {
                            "ancestry": {
                                "orgs": v.ancestry.orgs,
                                "teams": v.ancestry.teams,
                                "pillars": v.ancestry.pillars,
                                "team_groups": v.ancestry.team_groups,
                            }
                        }
                        for k, v in items.items()
                    }
                    for cat, items in data.indexes.membership.relationship_index.items()
                },
            },
            "slack_id_mappings": {
                "slack_uid_to_uid": data.indexes.slack_id_mappings.slack_uid_to_uid,
            },
            "github_id_mappings": {
                "github_id_to_uid": data.indexes.github_id_mappings.github_id_to_uid,
            },
        },
    }


def _employee_to_dict(emp: Employee) -> dict:
    """Convert Employee to dictionary."""
    d = {
        "uid": emp.uid,
        "full_name": emp.full_name,
        "email": emp.email,
        "job_title": emp.job_title,
    }
    if emp.slack_uid:
        d["slack_uid"] = emp.slack_uid
    if emp.github_id:
        d["github_id"] = emp.github_id
    if emp.rhat_geo:
        d["rhat_geo"] = emp.rhat_geo
    if emp.cost_center:
        d["cost_center"] = emp.cost_center
    if emp.manager_uid:
        d["manager_uid"] = emp.manager_uid
    if emp.is_people_manager:
        d["is_people_manager"] = emp.is_people_manager
    return d


def _group_to_dict(group: Group) -> dict:
    """Convert Group to dictionary."""
    d = {
        "type": {"name": group.type.name},
        "resolved_people_uid_list": group.resolved_people_uid_list,
    }
    if group.slack:
        d["slack"] = {
            "channels": [
                {
                    "channel": c.channel,
                    "channel_id": c.channel_id,
                    "description": c.description,
                    "types": c.types,
                }
                for c in group.slack.channels
            ],
            "aliases": [
                {"alias": a.alias, "description": a.description}
                for a in group.slack.aliases
            ],
        }
    if group.roles:
        d["roles"] = [{"people": r.people, "types": r.types} for r in group.roles]
    if group.jiras:
        d["jiras"] = [
            {
                "project": j.project,
                "component": j.component,
                "description": j.description,
                "view": j.view,
                "types": j.types,
            }
            for j in group.jiras
        ]
    if group.repos:
        d["repos"] = [
            {
                "repo": r.repo,
                "description": r.description,
                "tags": r.tags,
                "path": r.path,
                "roles": r.roles,
                "branch": r.branch,
                "types": r.types,
            }
            for r in group.repos
        ]
    if group.keywords:
        d["keywords"] = group.keywords
    if group.emails:
        d["emails"] = [
            {"address": e.address, "name": e.name, "description": e.description}
            for e in group.emails
        ]
    if group.resources:
        d["resources"] = [
            {"name": r.name, "url": r.url, "description": r.description}
            for r in group.resources
        ]
    if group.component_roles:
        d["component_roles"] = [
            {"component": c.component, "types": c.types} for c in group.component_roles
        ]
    return d


def _team_to_dict(team: Team) -> dict:
    """Convert Team to dictionary."""
    d = {
        "uid": team.uid,
        "name": team.name,
        "type": team.type,
        "group": _group_to_dict(team.group),
    }
    if team.tab_name:
        d["tab_name"] = team.tab_name
    if team.description:
        d["description"] = team.description
    return d


def _org_to_dict(org: Org) -> dict:
    """Convert Org to dictionary."""
    d = {
        "uid": org.uid,
        "name": org.name,
        "type": org.type,
        "group": _group_to_dict(org.group),
    }
    if org.tab_name:
        d["tab_name"] = org.tab_name
    if org.description:
        d["description"] = org.description
    return d


def _pillar_to_dict(pillar) -> dict:
    """Convert Pillar to dictionary."""
    d = {
        "uid": pillar.uid,
        "name": pillar.name,
        "type": pillar.type,
        "group": _group_to_dict(pillar.group),
    }
    if pillar.tab_name:
        d["tab_name"] = pillar.tab_name
    if pillar.description:
        d["description"] = pillar.description
    return d


def _team_group_to_dict(team_group) -> dict:
    """Convert TeamGroup to dictionary."""
    d = {
        "uid": team_group.uid,
        "name": team_group.name,
        "type": team_group.type,
        "group": _group_to_dict(team_group.group),
    }
    if team_group.tab_name:
        d["tab_name"] = team_group.tab_name
    if team_group.description:
        d["description"] = team_group.description
    return d


def assert_employee_equal(
    actual: Optional[Employee], expected: Optional[Employee], context: str = ""
) -> None:
    """Compare two employees for testing.

    Raises:
        AssertionError: If employees don't match.
    """
    if actual is None and expected is None:
        return

    if actual is None or expected is None:
        raise AssertionError(f"{context}: got {actual}, expected {expected}")

    if actual.uid != expected.uid:
        raise AssertionError(
            f"{context}: UID got {actual.uid!r}, expected {expected.uid!r}"
        )
    if actual.full_name != expected.full_name:
        raise AssertionError(
            f"{context}: FullName got {actual.full_name!r}, expected {expected.full_name!r}"
        )
    if actual.email != expected.email:
        raise AssertionError(
            f"{context}: Email got {actual.email!r}, expected {expected.email!r}"
        )
    if actual.job_title != expected.job_title:
        raise AssertionError(
            f"{context}: JobTitle got {actual.job_title!r}, expected {expected.job_title!r}"
        )
    if actual.slack_uid != expected.slack_uid:
        raise AssertionError(
            f"{context}: SlackUID got {actual.slack_uid!r}, expected {expected.slack_uid!r}"
        )

