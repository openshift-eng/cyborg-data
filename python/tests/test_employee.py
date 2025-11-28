"""Tests for employee-related functionality."""

import pytest

from orgdatacore import Service, Employee


class TestGetEmployeeByUID:
    """Tests for employee lookup by UID."""

    @pytest.mark.parametrize("uid,expected", [
        (
            "jsmith",
            Employee(
                uid="jsmith",
                full_name="John Smith",
                email="jsmith@example.com",
                job_title="Software Engineer",
                slack_uid="U12345678",
                github_id="jsmith-dev",
                manager_uid="adoe",
            ),
        ),
        (
            "adoe",
            Employee(
                uid="adoe",
                full_name="Alice Doe",
                email="adoe@example.com",
                job_title="Team Lead",
                slack_uid="U87654321",
                github_id="alice-codes",
                is_people_manager=True,
            ),
        ),
        ("nonexistent", None),
        ("", None),
    ])
    def test_get_employee_by_uid(self, service: Service, uid: str, expected: Employee | None):
        """Test employee lookup by UID."""
        result = service.get_employee_by_uid(uid)
        assert result == expected


class TestGetEmployeeBySlackID:
    """Tests for employee lookup by Slack ID."""

    @pytest.mark.parametrize("slack_id,expected_uid", [
        ("U12345678", "jsmith"),
        ("U87654321", "adoe"),
        ("U98765432", "bwilson"),
        ("U99999999", None),
        ("", None),
    ])
    def test_get_employee_by_slack_id(
        self, service: Service, slack_id: str, expected_uid: str | None
    ):
        """Test employee lookup by Slack ID."""
        result = service.get_employee_by_slack_id(slack_id)
        
        if expected_uid is None:
            assert result is None
        else:
            assert result is not None
            assert result.uid == expected_uid


class TestGetEmployeeByGitHubID:
    """Tests for employee lookup by GitHub ID."""

    @pytest.mark.parametrize("github_id,expected_uid", [
        ("jsmith-dev", "jsmith"),
        ("alice-codes", "adoe"),
        ("bobw", "bwilson"),
        ("hackerx", None),
        ("", None),
    ])
    def test_get_employee_by_github_id(
        self, service: Service, github_id: str, expected_uid: str | None
    ):
        """Test employee lookup by GitHub ID."""
        result = service.get_employee_by_github_id(github_id)
        
        if expected_uid is None:
            assert result is None
        else:
            assert result is not None
            assert result.uid == expected_uid


class TestEmployeeFields:
    """Tests that all employee fields are properly loaded."""

    def test_all_fields_populated(self, service: Service):
        """Test that all employee fields are populated correctly."""
        emp = service.get_employee_by_uid("jsmith")
        assert emp is not None
        
        assert emp.uid == "jsmith"
        assert emp.full_name == "John Smith"
        assert emp.email == "jsmith@example.com"
        assert emp.job_title == "Software Engineer"
        assert emp.slack_uid == "U12345678"
        assert emp.github_id == "jsmith-dev"


class TestSlackIDMapping:
    """Tests for bidirectional Slack ID mapping."""

    @pytest.mark.parametrize("uid,slack_id", [
        ("jsmith", "U12345678"),
        ("adoe", "U87654321"),
        ("bwilson", "U98765432"),
    ])
    def test_bidirectional_mapping(self, service: Service, uid: str, slack_id: str):
        """Test UID <-> Slack ID mapping consistency."""
        # Test UID -> Employee -> SlackID
        emp = service.get_employee_by_uid(uid)
        assert emp is not None
        assert emp.slack_uid == slack_id
        
        # Test SlackID -> Employee -> UID
        emp_by_slack = service.get_employee_by_slack_id(slack_id)
        assert emp_by_slack is not None
        assert emp_by_slack.uid == uid
        
        # Ensure they're the same employee
        assert emp == emp_by_slack


class TestGitHubIDMapping:
    """Tests for bidirectional GitHub ID mapping."""

    @pytest.mark.parametrize("uid,github_id", [
        ("jsmith", "jsmith-dev"),
        ("adoe", "alice-codes"),
        ("bwilson", "bobw"),
    ])
    def test_bidirectional_mapping(self, service: Service, uid: str, github_id: str):
        """Test UID <-> GitHub ID mapping consistency."""
        # Test UID -> Employee -> GitHubID
        emp = service.get_employee_by_uid(uid)
        assert emp is not None
        assert emp.github_id == github_id
        
        # Test GitHubID -> Employee -> UID
        emp_by_github = service.get_employee_by_github_id(github_id)
        assert emp_by_github is not None
        assert emp_by_github.uid == uid
        
        # Ensure they're the same employee
        assert emp == emp_by_github


class TestNewEmployeeFields:
    """Tests for the new employee fields added in refactoring."""

    def test_new_employee_fields(self):
        """Test that new employee fields are properly handled."""
        from orgdatacore.types import Data, Lookups, Indexes, MembershipIndex, SlackIDMappings, GitHubIDMappings
        
        service = Service()
        service._data = Data(
            lookups=Lookups(
                employees={
                    "testuser": Employee(
                        uid="testuser",
                        full_name="Test User",
                        email="test@example.com",
                        job_title="Engineer",
                        slack_uid="U123",
                        github_id="testgithub",
                        rhat_geo="NA",
                        cost_center=12345,
                        manager_uid="manager1",
                        is_people_manager=False,
                    ),
                },
            ),
            indexes=Indexes(
                membership=MembershipIndex(),
                slack_id_mappings=SlackIDMappings(),
                github_id_mappings=GitHubIDMappings(),
            ),
        )

        emp = service.get_employee_by_uid("testuser")
        assert emp is not None
        
        assert emp.github_id == "testgithub"
        assert emp.rhat_geo == "NA"
        assert emp.cost_center == 12345
        assert emp.manager_uid == "manager1"
        assert emp.is_people_manager is False


class TestGetManagerForEmployee:
    """Tests for manager lookup functionality."""

    @pytest.mark.parametrize("uid,expected_manager_uid", [
        ("jsmith", "adoe"),  # jsmith's manager is adoe
        ("bwilson", None),   # bwilson has no manager
        ("adoe", None),      # adoe has no manager
        ("nonexistent", None),
        ("", None),
    ])
    def test_get_manager_for_employee(
        self, service: Service, uid: str, expected_manager_uid: str | None
    ):
        """Test manager lookup for employees."""
        result = service.get_manager_for_employee(uid)
        
        if expected_manager_uid is None:
            assert result is None
        else:
            assert result is not None
            assert result.uid == expected_manager_uid


