"""Tests for organization-related functionality."""

import pytest

from orgdatacore import Service, OrgInfo


class TestGetOrgByName:
    """Tests for organization lookup by name."""

    @pytest.mark.parametrize("org_name,expected_found,expected_name", [
        ("test-org", True, "test-org"),
        ("platform-org", True, "platform-org"),
        ("nonexistent-org", False, None),
    ])
    def test_get_org_by_name(
        self, service: Service, org_name: str, expected_found: bool, expected_name: str | None
    ):
        """Test organization lookup by name."""
        result = service.get_org_by_name(org_name)
        
        if expected_found:
            assert result is not None
            assert result.name == expected_name
        else:
            assert result is None


class TestIsEmployeeInOrg:
    """Tests for organization membership checks."""

    @pytest.mark.parametrize("uid,org_name,expected", [
        ("jsmith", "test-org", True),  # Direct membership
        ("bwilson", "platform-org", True),  # Direct membership
        ("bwilson", "test-org", True),  # Via team inheritance
        ("jsmith", "platform-org", False),  # Not in platform-org
        ("nonexistent", "test-org", False),
        ("jsmith", "nonexistent-org", False),
    ])
    def test_is_employee_in_org(
        self, service: Service, uid: str, org_name: str, expected: bool
    ):
        """Test organization membership checks."""
        result = service.is_employee_in_org(uid, org_name)
        assert result == expected


class TestIsSlackUserInOrg:
    """Tests for Slack user organization membership checks."""

    @pytest.mark.parametrize("slack_id,org_name,expected", [
        ("U12345678", "test-org", True),  # jsmith
        ("U98765432", "platform-org", True),  # bwilson
        ("U98765432", "test-org", True),  # bwilson via team
        ("U99999999", "test-org", False),  # nonexistent
    ])
    def test_is_slack_user_in_org(
        self, service: Service, slack_id: str, org_name: str, expected: bool
    ):
        """Test Slack user organization membership checks."""
        result = service.is_slack_user_in_org(slack_id, org_name)
        assert result == expected


class TestGetUserOrganizations:
    """Tests for complete organizational hierarchy retrieval."""

    def test_jsmith_organizations(self, service: Service):
        """Test jsmith's organizational hierarchy."""
        result = service.get_user_organizations("U12345678")  # jsmith
        
        # Should contain these items
        expected_items = [
            OrgInfo(name="test-team", type="Team"),
            OrgInfo(name="test-org", type="Organization"),
        ]
        
        for expected in expected_items:
            found = any(
                item.name == expected.name and item.type == expected.type
                for item in result
            )
            assert found, f"Missing expected item: {expected}"

    def test_bwilson_organizations(self, service: Service):
        """Test bwilson's organizational hierarchy."""
        result = service.get_user_organizations("U98765432")  # bwilson
        
        # Should contain these items
        expected_items = [
            OrgInfo(name="platform-team", type="Team"),
            OrgInfo(name="platform-org", type="Organization"),
            OrgInfo(name="test-org", type="Organization"),
            OrgInfo(name="engineering", type="Pillar"),
            OrgInfo(name="backend-teams", type="Team Group"),
        ]
        
        for expected in expected_items:
            found = any(
                item.name == expected.name and item.type == expected.type
                for item in result
            )
            assert found, f"Missing expected item: {expected}"

    def test_nonexistent_user_organizations(self, service: Service):
        """Test organizational hierarchy for nonexistent user."""
        result = service.get_user_organizations("U99999999")
        assert len(result) == 0

    def test_no_duplicate_organizations(self, service: Service):
        """Test that no duplicate organizations are returned."""
        result = service.get_user_organizations("U98765432")  # bwilson
        
        seen = set()
        for org in result:
            key = f"{org.name}:{org.type}"
            assert key not in seen, f"Duplicate organization: {org}"
            seen.add(key)


class TestOrganizationalHierarchy:
    """Tests for team-to-org inheritance."""

    def test_direct_org_membership(self, service: Service):
        """Test that bwilson is in platform-org directly."""
        assert service.is_employee_in_org("bwilson", "platform-org")

    def test_inherited_org_membership(self, service: Service):
        """Test that bwilson is in test-org via team hierarchy."""
        assert service.is_employee_in_org("bwilson", "test-org")

    def test_jsmith_in_test_org(self, service: Service):
        """Test that jsmith is in test-org."""
        assert service.is_employee_in_org("jsmith", "test-org")

    def test_jsmith_not_in_platform_org(self, service: Service):
        """Test that jsmith is NOT in platform-org."""
        assert not service.is_employee_in_org("jsmith", "platform-org")


class TestOrgInfoTypes:
    """Tests that correct OrgInfo types are returned."""

    def test_org_info_types(self, service: Service):
        """Test that OrgInfo types are correct."""
        orgs = service.get_user_organizations("U98765432")  # bwilson
        
        type_map = {org.name: org.type for org in orgs}
        
        expected_types = {
            "platform-team": "Team",
            "platform-org": "Organization",
            "test-org": "Organization",
            "engineering": "Pillar",
            "backend-teams": "Team Group",
        }
        
        for name, expected_type in expected_types.items():
            actual_type = type_map.get(name)
            assert actual_type is not None, f"Expected to find {name} in user organizations"
            assert actual_type == expected_type, \
                f"Expected {name} to have type {expected_type}, got {actual_type}"

