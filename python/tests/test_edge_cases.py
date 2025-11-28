"""Tests for edge cases and error handling."""

import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from orgdatacore import Service

# Import from internal testing module - NOT part of public API
from orgdatacore.internal.testing import FileDataSource, FakeDataSource


class TestServiceWithNoData:
    """Tests for service behavior before data is loaded."""

    def test_get_employee_by_uid_returns_none(self, empty_service: Service):
        """GetEmployeeByUID should return None with no data loaded."""
        assert empty_service.get_employee_by_uid("test") is None

    def test_get_employee_by_slack_id_returns_none(self, empty_service: Service):
        """GetEmployeeBySlackID should return None with no data loaded."""
        assert empty_service.get_employee_by_slack_id("U123") is None

    def test_get_employee_by_github_id_returns_none(self, empty_service: Service):
        """GetEmployeeByGitHubID should return None with no data loaded."""
        assert empty_service.get_employee_by_github_id("ghuser") is None

    def test_get_team_by_name_returns_none(self, empty_service: Service):
        """GetTeamByName should return None with no data loaded."""
        assert empty_service.get_team_by_name("test") is None

    def test_get_org_by_name_returns_none(self, empty_service: Service):
        """GetOrgByName should return None with no data loaded."""
        assert empty_service.get_org_by_name("test") is None

    def test_get_teams_for_uid_returns_empty(self, empty_service: Service):
        """GetTeamsForUID should return empty list with no data loaded."""
        assert empty_service.get_teams_for_uid("test") == []

    def test_get_team_members_returns_empty(self, empty_service: Service):
        """GetTeamMembers should return empty list with no data loaded."""
        assert empty_service.get_team_members("test") == []

    def test_is_employee_in_team_returns_false(self, empty_service: Service):
        """IsEmployeeInTeam should return False with no data loaded."""
        assert empty_service.is_employee_in_team("test", "test") is False

    def test_is_employee_in_org_returns_false(self, empty_service: Service):
        """IsEmployeeInOrg should return False with no data loaded."""
        assert empty_service.is_employee_in_org("test", "test") is False

    def test_get_user_organizations_returns_empty(self, empty_service: Service):
        """GetUserOrganizations should return empty list with no data loaded."""
        assert empty_service.get_user_organizations("U123") == []


class TestServiceErrorHandling:
    """Tests for various error conditions."""

    def test_empty_string_handling(self, service: Service):
        """Test that empty string parameters are handled correctly."""
        assert service.get_employee_by_uid("") is None
        assert service.get_employee_by_slack_id("") is None
        assert service.get_employee_by_github_id("") is None
        assert service.get_team_by_name("") is None
        assert service.get_org_by_name("") is None

    def test_nonexistent_data_handling(self, service: Service):
        """Test that nonexistent data queries return safe defaults."""
        teams = service.get_teams_for_uid("nonexistent")
        assert len(teams) == 0

        members = service.get_team_members("nonexistent-team")
        assert len(members) == 0

        orgs = service.get_user_organizations("U99999999")
        assert len(orgs) == 0

    def test_special_characters_in_ids(self, service: Service):
        """Test that special characters in IDs don't cause crashes."""
        # These should not raise exceptions
        service.get_employee_by_uid("user@domain.com")
        service.get_team_by_name("team-with-dashes_and_underscores")
        service.get_org_by_name("org.with.dots")
        service.is_employee_in_team("user-123", "team_456")


class TestConcurrentAccess:
    """Tests for thread safety of the service."""

    def test_concurrent_reads(self, service: Service):
        """Test that concurrent reads are safe."""
        results = []
        errors = []

        def reader(thread_id: int) -> None:
            try:
                for _ in range(100):
                    service.get_employee_by_uid("jsmith")
                    service.get_team_by_name("test-team")
                    service.is_employee_in_team("jsmith", "test-team")
                    service.get_version()
                    service.get_user_organizations("U12345678")
                results.append(thread_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=5)
        
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10

    def test_concurrent_read_write(self, test_data_path: Path):
        """Test that concurrent reads and writes are safe."""
        service = Service()
        file_source = FileDataSource(str(test_data_path))
        
        # Initial load
        service.load_from_data_source(file_source)
        
        results = []
        errors = []

        def reader() -> None:
            try:
                for _ in range(100):
                    service.get_employee_by_uid("jsmith")
                    service.get_team_members("test-team")
                    time.sleep(0.001)
                results.append("reader")
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                for _ in range(5):
                    time.sleep(0.05)
                    service.load_from_data_source(file_source)
                results.append("writer")
            except Exception as e:
                errors.append(e)

        # Start 10 readers and 1 writer
        threads = [threading.Thread(target=reader) for _ in range(10)]
        threads.append(threading.Thread(target=writer))
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=10)
        
        assert len(errors) == 0, f"Errors occurred: {errors}"


class TestReloadData:
    """Tests for data reloading."""

    def test_reload_data(self, test_data_path: Path):
        """Test that data can be reloaded."""
        service = Service()
        
        # Initial state - no data
        version1 = service.get_version()
        assert version1.employee_count == 0
        
        # Load data for the first time
        file_source = FileDataSource(str(test_data_path))
        service.load_from_data_source(file_source)
        
        version2 = service.get_version()
        assert version2.employee_count == 3
        assert version2.load_time > version1.load_time
        
        # Reload the same data
        time.sleep(0.001)  # Ensure time difference
        service.load_from_data_source(file_source)
        
        version3 = service.get_version()
        assert version3.employee_count == 3
        assert version3.load_time > version2.load_time
        
        # Data should still be accessible
        emp = service.get_employee_by_uid("jsmith")
        assert emp is not None


class TestEnumerationMethods:
    """Tests for enumeration methods."""

    def test_get_all_employee_uids(self, service: Service):
        """Test getting all employee UIDs."""
        uids = service.get_all_employee_uids()
        assert len(uids) == 3
        assert "jsmith" in uids
        assert "adoe" in uids
        assert "bwilson" in uids

    def test_get_all_team_names(self, service: Service):
        """Test getting all team names."""
        names = service.get_all_team_names()
        assert len(names) == 2
        assert "test-team" in names
        assert "platform-team" in names

    def test_get_all_org_names(self, service: Service):
        """Test getting all organization names."""
        names = service.get_all_org_names()
        assert len(names) == 2
        assert "test-org" in names
        assert "platform-org" in names

    def test_get_all_pillar_names(self, service: Service):
        """Test getting all pillar names."""
        names = service.get_all_pillar_names()
        assert len(names) == 1
        assert "engineering" in names

    def test_get_all_team_group_names(self, service: Service):
        """Test getting all team group names."""
        names = service.get_all_team_group_names()
        assert len(names) == 1
        assert "backend-teams" in names

    def test_enumeration_with_no_data(self, empty_service: Service):
        """Test enumeration methods with no data loaded."""
        assert empty_service.get_all_employee_uids() == []
        assert empty_service.get_all_team_names() == []
        assert empty_service.get_all_org_names() == []
        assert empty_service.get_all_pillar_names() == []
        assert empty_service.get_all_team_group_names() == []

