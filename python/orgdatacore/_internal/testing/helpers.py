"""Test helpers for orgdatacore."""

import json
from collections.abc import Callable
from io import BytesIO
from typing import Any, BinaryIO

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
    return _data_to_json(data)


def _data_to_json(data: Data) -> str:
    """Convert Data to JSON string."""
    return json.dumps(_data_to_dict(data))


def _data_to_dict(data: Data) -> dict[str, Any]:
    """Convert Data to dictionary for JSON serialization."""
    result: dict[str, Any] = {
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
            "components": {
                k: _component_to_dict(v) for k, v in data.lookups.components.items()
            },
        },
        "indexes": {
            "membership": {
                "membership_index": {
                    k: [{"name": m.name, "type": m.type} for m in v]
                    for k, v in data.indexes.membership.membership_index.items()
                },
            },
            "slack_id_mappings": {
                "slack_uid_to_uid": dict(
                    data.indexes.slack_id_mappings.slack_uid_to_uid
                ),
            },
            "github_id_mappings": {
                "github_id_to_uid": dict(
                    data.indexes.github_id_mappings.github_id_to_uid
                ),
            },
        },
    }
    # Add jira index if present
    if data.indexes.jira.project_component_owners:
        result["indexes"]["jira"] = {
            project: {
                component: [{"name": o.name, "type": o.type} for o in owners]
                for component, owners in components.items()
            }
            for project, components in data.indexes.jira.project_component_owners.items()
        }
    return result


def _component_to_dict(component: Component) -> dict[str, Any]:
    """Convert Component to dictionary."""
    d: dict[str, Any] = {
        "name": component.name,
    }
    if component.type:
        d["type"] = component.type
    if component.description:
        d["description"] = component.description
    return d


def _employee_to_dict(emp: Employee) -> dict[str, Any]:
    """Convert Employee to dictionary."""
    d: dict[str, Any] = {
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


def _group_to_dict(group: Group) -> dict[str, Any]:
    """Convert Group to dictionary."""
    d: dict[str, Any] = {
        "type": {"name": group.type.name},
        "resolved_people_uid_list": list(group.resolved_people_uid_list),
    }
    if group.slack:
        d["slack"] = {
            "channels": [
                {
                    "channel": c.channel,
                    "channel_id": c.channel_id,
                    "description": c.description,
                    "types": list(c.types),
                }
                for c in group.slack.channels
            ],
            "aliases": [
                {"alias": a.alias, "description": a.description}
                for a in group.slack.aliases
            ],
        }
    if group.roles:
        d["roles"] = [
            {"people": list(r.people), "types": list(r.types)} for r in group.roles
        ]
    if group.jiras:
        d["jiras"] = [
            {
                "project": j.project,
                "component": j.component,
                "description": j.description,
                "view": j.view,
                "types": list(j.types),
            }
            for j in group.jiras
        ]
    if group.repos:
        d["repos"] = [
            {
                "repo_name": r.repo,
                "description": r.description,
                "tags": list(r.tags),
                "path": r.path,
                "roles": list(r.roles),
                "branch": r.branch,
                "types": list(r.types),
            }
            for r in group.repos
        ]
    if group.keywords:
        d["keywords"] = list(group.keywords)
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
            {"component": c.component, "types": list(c.types)}
            for c in group.component_roles
        ]
    return d


def _team_to_dict(team: Team) -> dict[str, Any]:
    """Convert Team to dictionary."""
    d: dict[str, Any] = {
        "uid": team.uid,
        "name": team.name,
        "type": team.type,
        "group": _group_to_dict(team.group),
    }
    if team.tab_name:
        d["tab_name"] = team.tab_name
    if team.description:
        d["description"] = team.description
    if team.parent:
        d["parent"] = {"name": team.parent.name, "type": team.parent.type}
    return d


def _org_to_dict(org: Org) -> dict[str, Any]:
    """Convert Org to dictionary."""
    d: dict[str, Any] = {
        "uid": org.uid,
        "name": org.name,
        "type": org.type,
        "group": _group_to_dict(org.group),
    }
    if org.tab_name:
        d["tab_name"] = org.tab_name
    if org.description:
        d["description"] = org.description
    if org.parent:
        d["parent"] = {"name": org.parent.name, "type": org.parent.type}
    return d


def _pillar_to_dict(pillar: Pillar) -> dict[str, Any]:
    """Convert Pillar to dictionary."""
    d: dict[str, Any] = {
        "uid": pillar.uid,
        "name": pillar.name,
        "type": pillar.type,
        "group": _group_to_dict(pillar.group),
    }
    if pillar.tab_name:
        d["tab_name"] = pillar.tab_name
    if pillar.description:
        d["description"] = pillar.description
    if pillar.parent:
        d["parent"] = {"name": pillar.parent.name, "type": pillar.parent.type}
    return d


def _team_group_to_dict(team_group: TeamGroup) -> dict[str, Any]:
    """Convert TeamGroup to dictionary."""
    d: dict[str, Any] = {
        "uid": team_group.uid,
        "name": team_group.name,
        "type": team_group.type,
        "group": _group_to_dict(team_group.group),
    }
    if team_group.tab_name:
        d["tab_name"] = team_group.tab_name
    if team_group.description:
        d["description"] = team_group.description
    if team_group.parent:
        d["parent"] = {"name": team_group.parent.name, "type": team_group.parent.type}
    return d
