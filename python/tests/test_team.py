"""Tests for team-related functionality."""

import pytest

from orgdatacore import (
    AliasInfo,
    ChannelInfo,
    Data,
    EmailInfo,
    EscalationContactInfo,
    GitHubIDMappings,
    Group,
    GroupType,
    Indexes,
    JiraInfo,
    Lookups,
    MembershipIndex,
    RepoInfo,
    ResourceInfo,
    RoleInfo,
    Service,
    SlackConfig,
    SlackIDMappings,
    Team,
)


class TestGetTeamByName:
    """Tests for team lookup by name."""

    @pytest.mark.parametrize(
        "team_name,expected_found,expected_name",
        [
            ("test-team", True, "test-team"),
            ("platform-team", True, "platform-team"),
            ("nonexistent-team", False, None),
            ("", False, None),
        ],
    )
    def test_get_team_by_name(
        self,
        service: Service,
        team_name: str,
        expected_found: bool,
        expected_name: str | None,
    ):
        """Test team lookup by name."""
        result = service.get_team_by_name(team_name)

        if expected_found:
            assert result is not None
            assert result.name == expected_name
        else:
            assert result is None


class TestGetTeamsBySlackChannel:
    """Tests for team lookup by Slack channel name."""

    @pytest.mark.parametrize(
        "channel,expected_names",
        [
            ("#test-team", ["test-team"]),
            ("platform", ["platform-team"]),
            ("test-alerts", ["test-team"]),
            ("#Test-Team", ["test-team"]),
            ("nonexistent", []),
            ("", []),
            ("  #test-team  ", ["test-team"]),
            ("#", []),
        ],
    )
    def test_get_teams_by_slack_channel(
        self,
        service: Service,
        channel: str,
        expected_names: list[str],
    ):
        """Test team lookup by Slack channel name."""
        result = service.get_teams_by_slack_channel(channel)
        result_names = sorted(t.name for t in result)
        assert result_names == sorted(expected_names)


class TestGetTeamsForUID:
    """Tests for team membership lookup by UID."""

    @pytest.mark.parametrize(
        "uid,expected_teams",
        [
            ("jsmith", ["test-team"]),
            ("bwilson", ["platform-team"]),
            ("nonexistent", []),
        ],
    )
    def test_get_teams_for_uid(
        self, service: Service, uid: str, expected_teams: list[str]
    ):
        """Test team membership lookup by UID."""
        result = service.get_teams_for_uid(uid)

        assert sorted(result) == sorted(expected_teams)


class TestGetTeamsForSlackID:
    """Tests for team membership lookup by Slack ID."""

    @pytest.mark.parametrize(
        "slack_id,expected_teams",
        [
            ("U12345678", ["test-team"]),  # jsmith
            ("U98765432", ["platform-team"]),  # bwilson
            ("U99999999", []),  # nonexistent
        ],
    )
    def test_get_teams_for_slack_id(
        self, service: Service, slack_id: str, expected_teams: list[str]
    ):
        """Test team membership lookup by Slack ID."""
        result = service.get_teams_for_slack_id(slack_id)

        assert sorted(result) == sorted(expected_teams)


class TestGetTeamMembers:
    """Tests for team member retrieval."""

    @pytest.mark.parametrize(
        "team_name,expected_uids",
        [
            ("test-team", ["jsmith", "adoe"]),
            ("platform-team", ["bwilson"]),
            ("nonexistent-team", []),
        ],
    )
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

    @pytest.mark.parametrize(
        "uid,team_name,expected",
        [
            ("jsmith", "test-team", True),
            ("bwilson", "platform-team", True),
            ("jsmith", "platform-team", False),
            ("nonexistent", "test-team", False),
            ("jsmith", "nonexistent-team", False),
        ],
    )
    def test_is_employee_in_team(
        self, service: Service, uid: str, team_name: str, expected: bool
    ):
        """Test team membership checks."""
        result = service.is_employee_in_team(uid, team_name)
        assert result == expected


class TestIsSlackUserInTeam:
    """Tests for Slack user team membership checks."""

    @pytest.mark.parametrize(
        "slack_id,team_name,expected",
        [
            ("U12345678", "test-team", True),  # jsmith
            ("U98765432", "platform-team", True),  # bwilson
            ("U12345678", "platform-team", False),  # jsmith
            ("U99999999", "test-team", False),  # nonexistent
        ],
    )
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
            assert "test-team" in teams, (
                f"Employee {member.uid} is member of test-team but get_teams_for_uid doesn't show it"
            )

            # is_employee_in_team should also return True
            assert service.is_employee_in_team(member.uid, "test-team"), (
                f"Employee {member.uid} is member of test-team but is_employee_in_team returns False"
            )


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
                            resolved_people_uid_list=("user1",),
                            slack=SlackConfig(
                                channels=(
                                    ChannelInfo(
                                        channel="team-backend",
                                        channel_id="C123",
                                        description="Main channel",
                                        types=("team-internal",),
                                    ),
                                ),
                                aliases=(
                                    AliasInfo(
                                        alias="@backend-team",
                                        description="Team alias",
                                    ),
                                ),
                            ),
                            roles=(
                                RoleInfo(
                                    people=("manager1",),
                                    roles=("manager",),
                                ),
                            ),
                            jiras=(
                                JiraInfo(
                                    project="BACKEND",
                                    component="API",
                                    description="Backend API",
                                    types=("main",),
                                ),
                            ),
                            repos=(
                                RepoInfo(
                                    repo="https://github.com/org/backend",
                                    description="Main backend repo",
                                    types=("source",),
                                ),
                            ),
                            keywords=("backend", "api"),
                            emails=(
                                EmailInfo(
                                    address="backend@example.com",
                                    name="Team Email",
                                    description="Backend team email",
                                ),
                            ),
                            resources=(
                                ResourceInfo(
                                    name="Wiki",
                                    url="https://wiki.example.com",
                                    description="Team wiki",
                                ),
                            ),
                            component_roles=("/component/path",),
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


class TestGetComponentsForTeam:
    """Tests for get_components_for_team."""

    def test_returns_components_with_ownership_types(self, service: Service):
        components = service.get_components_for_team("platform-team")
        assert len(components) == 2
        by_name = {c.component: c for c in components}
        assert "platform-api" in by_name
        assert "auth-service" in by_name
        assert "owner" in by_name["platform-api"].ownership_types
        assert "contributor" in by_name["auth-service"].ownership_types

    def test_single_component_team(self, service: Service):
        components = service.get_components_for_team("test-team")
        assert len(components) == 1
        assert components[0].component == "auth-service"
        assert "owner" in components[0].ownership_types

    def test_unknown_team_returns_empty(self, service: Service):
        components = service.get_components_for_team("nonexistent-team")
        assert components == []

    def test_empty_service_returns_empty(self, empty_service: Service):
        components = empty_service.get_components_for_team("test-team")
        assert components == []


class TestGetTeamEscalation:
    """Tests for team escalation contact lookup."""

    def test_returns_escalation_contacts(self, service: Service):
        """Test that escalation contacts are returned for a team that has them."""
        result = service.get_team_escalation("platform-team")

        assert len(result) == 2
        assert result[0].name == "Platform on-call"
        assert result[0].url == "https://redhat.enterprise.slack.com/archives/C003"
        assert (
            result[0].description == "Primary on-call engineer for platform incidents."
        )
        assert result[1].name == "Platform team"

    def test_returns_empty_for_team_without_escalation(self, service: Service):
        """Test that empty list is returned for a team with no escalation data."""
        result = service.get_team_escalation("test-team")

        assert result == []

    def test_returns_empty_for_nonexistent_team(self, service: Service):
        """Test that empty list is returned for a nonexistent team."""
        result = service.get_team_escalation("nonexistent-team")

        assert result == []

    def test_returns_empty_for_empty_service(self, empty_service: Service):
        """Test that empty list is returned when no data is loaded."""
        result = empty_service.get_team_escalation("platform-team")

        assert result == []

    def test_escalation_contacts_are_ordered(self, service: Service):
        """Test that escalation contacts preserve insertion order."""
        result = service.get_team_escalation("platform-team")

        names = [c.name for c in result]
        assert names == ["Platform on-call", "Platform team"]

    def test_escalation_contact_fields(self):
        """Test EscalationContactInfo dataclass fields."""
        contact = EscalationContactInfo(
            name="Test monitor",
            url="https://example.com/channel",
            description="Test escalation path",
        )

        assert contact.name == "Test monitor"
        assert contact.url == "https://example.com/channel"
        assert contact.description == "Test escalation path"
