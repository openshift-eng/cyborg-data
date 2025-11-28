"""Tests for team-related functionality."""

import pytest

from orgdatacore import Service
from orgdatacore.types import (
    Data, Lookups, Indexes, Team, Group, GroupType, MembershipIndex,
    SlackIDMappings, GitHubIDMappings, SlackConfig, ChannelInfo, AliasInfo,
    RoleInfo, JiraInfo, RepoInfo, EmailInfo, ResourceInfo, ComponentRoleInfo,
)


class TestGetTeamByName:
    """Tests for team lookup by name."""

    @pytest.mark.parametrize("team_name,expected_found,expected_name", [
        ("test-team", True, "test-team"),
        ("platform-team", True, "platform-team"),
        ("nonexistent-team", False, None),
        ("", False, None),
    ])
    def test_get_team_by_name(
        self, service: Service, team_name: str, expected_found: bool, expected_name: str | None
    ):
        """Test team lookup by name."""
        result = service.get_team_by_name(team_name)
        
        if expected_found:
            assert result is not None
            assert result.name == expected_name
        else:
            assert result is None


class TestGetTeamsForUID:
    """Tests for team membership lookup by UID."""

    @pytest.mark.parametrize("uid,expected_teams", [
        ("jsmith", ["test-team"]),
        ("bwilson", ["platform-team"]),
        ("nonexistent", []),
    ])
    def test_get_teams_for_uid(
        self, service: Service, uid: str, expected_teams: list[str]
    ):
        """Test team membership lookup by UID."""
        result = service.get_teams_for_uid(uid)
        
        assert sorted(result) == sorted(expected_teams)


class TestGetTeamsForSlackID:
    """Tests for team membership lookup by Slack ID."""

    @pytest.mark.parametrize("slack_id,expected_teams", [
        ("U12345678", ["test-team"]),  # jsmith
        ("U98765432", ["platform-team"]),  # bwilson
        ("U99999999", []),  # nonexistent
    ])
    def test_get_teams_for_slack_id(
        self, service: Service, slack_id: str, expected_teams: list[str]
    ):
        """Test team membership lookup by Slack ID."""
        result = service.get_teams_for_slack_id(slack_id)
        
        assert sorted(result) == sorted(expected_teams)


class TestGetTeamMembers:
    """Tests for team member retrieval."""

    @pytest.mark.parametrize("team_name,expected_uids", [
        ("test-team", ["jsmith", "adoe"]),
        ("platform-team", ["bwilson"]),
        ("nonexistent-team", []),
    ])
    def test_get_team_members(
        self, service: Service, team_name: str, expected_uids: list[str]
    ):
        """Test team member retrieval."""
        result = service.get_team_members(team_name)
        
        result_uids = [emp.uid for emp in result]
        assert sorted(result_uids) == sorted(expected_uids)

    def test_team_members_have_all_fields(self, service: Service):
        """Test that returned employees have all fields populated."""
        members = service.get_team_members("test-team")
        
        for emp in members:
            assert emp.uid != ""
            assert emp.full_name != ""
            assert emp.email != ""


class TestIsEmployeeInTeam:
    """Tests for team membership checks."""

    @pytest.mark.parametrize("uid,team_name,expected", [
        ("jsmith", "test-team", True),
        ("bwilson", "platform-team", True),
        ("jsmith", "platform-team", False),
        ("nonexistent", "test-team", False),
        ("jsmith", "nonexistent-team", False),
    ])
    def test_is_employee_in_team(
        self, service: Service, uid: str, team_name: str, expected: bool
    ):
        """Test team membership checks."""
        result = service.is_employee_in_team(uid, team_name)
        assert result == expected


class TestIsSlackUserInTeam:
    """Tests for Slack user team membership checks."""

    @pytest.mark.parametrize("slack_id,team_name,expected", [
        ("U12345678", "test-team", True),  # jsmith
        ("U98765432", "platform-team", True),  # bwilson
        ("U12345678", "platform-team", False),  # jsmith
        ("U99999999", "test-team", False),  # nonexistent
    ])
    def test_is_slack_user_in_team(
        self, service: Service, slack_id: str, team_name: str, expected: bool
    ):
        """Test Slack user team membership checks."""
        result = service.is_slack_user_in_team(slack_id, team_name)
        assert result == expected


class TestTeamMembershipConsistency:
    """Tests for consistency between different team queries."""

    def test_team_membership_consistency(self, service: Service):
        """Test that team membership is consistent across different queries."""
        members = service.get_team_members("test-team")
        
        for member in members:
            # Each member should show up in get_teams_for_uid
            teams = service.get_teams_for_uid(member.uid)
            assert "test-team" in teams, \
                f"Employee {member.uid} is member of test-team but get_teams_for_uid doesn't show it"
            
            # is_employee_in_team should also return True
            assert service.is_employee_in_team(member.uid, "test-team"), \
                f"Employee {member.uid} is member of test-team but is_employee_in_team returns False"


class TestGroupExtendedFields:
    """Tests for the extended Group fields added in refactoring."""

    def test_group_extended_fields(self):
        """Test that extended group fields are properly handled."""
        service = Service()
        service._data = Data(
            lookups=Lookups(
                teams={
                    "Backend Team": Team(
                        uid="team1",
                        name="Backend Team",
                        tab_name="Backend",
                        description="Backend development team",
                        type="team",
                        group=Group(
                            type=GroupType(name="team"),
                            resolved_people_uid_list=["user1"],
                            slack=SlackConfig(
                                channels=[
                                    ChannelInfo(
                                        channel="team-backend",
                                        channel_id="C123",
                                        description="Main channel",
                                        types=["team-internal"],
                                    ),
                                ],
                                aliases=[
                                    AliasInfo(
                                        alias="@backend-team",
                                        description="Team alias",
                                    ),
                                ],
                            ),
                            roles=[
                                RoleInfo(
                                    people=["manager1"],
                                    types=["manager"],
                                ),
                            ],
                            jiras=[
                                JiraInfo(
                                    project="BACKEND",
                                    component="API",
                                    description="Backend API",
                                    types=["main"],
                                ),
                            ],
                            repos=[
                                RepoInfo(
                                    repo="https://github.com/org/backend",
                                    description="Main backend repo",
                                    types=["source"],
                                ),
                            ],
                            keywords=["backend", "api"],
                            emails=[
                                EmailInfo(
                                    address="backend@example.com",
                                    name="Team Email",
                                    description="Backend team email",
                                ),
                            ],
                            resources=[
                                ResourceInfo(
                                    name="Wiki",
                                    url="https://wiki.example.com",
                                    description="Team wiki",
                                ),
                            ],
                            component_roles=[
                                ComponentRoleInfo(
                                    component="/component/path",
                                    types=["owner"],
                                ),
                            ],
                        ),
                    ),
                },
            ),
            indexes=Indexes(
                membership=MembershipIndex(),
                slack_id_mappings=SlackIDMappings(),
                github_id_mappings=GitHubIDMappings(),
            ),
        )

        team = service.get_team_by_name("Backend Team")
        assert team is not None
        
        assert team.tab_name == "Backend"
        assert team.description == "Backend development team"
        assert team.group.slack is not None
        assert len(team.group.slack.channels) == 1
        assert len(team.group.roles) == 1
        assert len(team.group.jiras) == 1
        assert len(team.group.repos) == 1
        assert len(team.group.keywords) == 2
        assert len(team.group.emails) == 1
        assert len(team.group.resources) == 1
        assert len(team.group.component_roles) == 1

