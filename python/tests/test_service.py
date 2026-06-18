"""Tests for the Service class - service initialization and data loading."""

from datetime import datetime
from pathlib import Path

import pytest

from orgdatacore import DataLoadError, Service

# Import from internal testing module - NOT part of public API
from orgdatacore._internal.testing import FakeDataSource, FileDataSource


@pytest.fixture
def pii_free_data_path() -> Path:
    """Get path to the PII-free test data file."""
    return Path(__file__).parent.parent.parent / "testdata" / "test_org_data_pii_free.json"


@pytest.fixture
def pii_free_service(pii_free_data_path: Path) -> Service:
    """Create a service loaded with PII-free test data."""
    svc = Service()
    file_source = FileDataSource(str(pii_free_data_path))
    svc.load_from_data_source(file_source)
    return svc


class TestNewService:
    """Tests for service creation."""

    def test_new_service_returns_instance(self):
        """NewService should return a valid service instance."""
        service = Service()
        assert service is not None

    def test_new_service_has_no_data(self, empty_service: Service):
        """New service should start with empty data."""
        version = empty_service.get_version()
        assert version.employee_count == 0
        assert version.org_count == 0

    def test_constructor_injection(self, test_data_path: Path) -> None:
        """Service should support constructor injection of data source (keyword-only)."""
        file_source = FileDataSource(str(test_data_path))

        # Constructor injection - must use keyword argument
        service = Service(data_source=file_source)

        version = service.get_version()
        assert version.employee_count == 3
        assert version.org_count == 2

        # Data should be queryable
        emp = service.get_employee_by_uid("jsmith")
        assert emp is not None
        assert emp.full_name == "John Smith"


class TestServiceInterface:
    """Tests to ensure Service implements ServiceInterface."""

    def test_service_implements_interface(self, service: Service):
        """Service should implement all required interface methods."""
        # Core data access methods
        assert hasattr(service, "get_employee_by_uid")
        assert hasattr(service, "get_employee_by_slack_id")
        assert hasattr(service, "get_employee_by_github_id")
        assert hasattr(service, "get_manager_for_employee")
        assert hasattr(service, "get_team_by_name")
        assert hasattr(service, "get_org_by_name")
        assert hasattr(service, "get_pillar_by_name")
        assert hasattr(service, "get_team_group_by_name")

        # Membership queries
        assert hasattr(service, "get_teams_for_uid")
        assert hasattr(service, "get_teams_for_slack_id")
        assert hasattr(service, "get_team_members")
        assert hasattr(service, "is_employee_in_team")
        assert hasattr(service, "is_slack_user_in_team")

        # Organization queries
        assert hasattr(service, "is_employee_in_org")
        assert hasattr(service, "is_slack_user_in_org")
        assert hasattr(service, "get_user_organizations")

        # Data management
        assert hasattr(service, "get_version")
        assert hasattr(service, "load_from_data_source")
        assert hasattr(service, "start_data_source_watcher")

        # Enumeration methods
        assert hasattr(service, "get_all_employee_uids")
        assert hasattr(service, "get_all_team_names")
        assert hasattr(service, "get_all_org_names")
        assert hasattr(service, "get_all_pillar_names")
        assert hasattr(service, "get_all_team_group_names")


class TestLoadFromDataSource:
    """Tests for data loading functionality."""

    def test_load_valid_data_file(self, test_data_path: Path):
        """Loading a valid data file should succeed."""
        service = Service()
        file_source = FileDataSource(str(test_data_path))

        # Should not raise
        service.load_from_data_source(file_source)

        version = service.get_version()
        assert version.employee_count == 3
        assert version.org_count == 2

    def test_load_nonexistent_file(self):
        """Loading a nonexistent file should raise DataLoadError."""
        service = Service()
        file_source = FileDataSource("nonexistent.json")

        with pytest.raises(DataLoadError, match="file not found"):
            service.load_from_data_source(file_source)

    def test_load_sets_version_info(self, service: Service):
        """Loading data should set version information."""
        version = service.get_version()

        assert version.employee_count == 3
        assert version.org_count == 2
        assert version.load_time != datetime.min


class TestGetVersion:
    """Tests for version information."""

    def test_initial_version_has_zero_values(self, empty_service: Service):
        """Initial version should have zero/default values."""
        version = empty_service.get_version()

        assert version.load_time == datetime.min
        assert version.employee_count == 0
        assert version.org_count == 0

    def test_version_after_loading(self, service: Service):
        """Version should be updated after loading data."""
        version = service.get_version()

        assert version.employee_count == 3
        assert version.org_count == 2


class TestInvalidJSONHandling:
    """Tests for handling invalid JSON data."""

    def test_invalid_json_raises_error(self, empty_service: Service):
        """Loading invalid JSON should raise DataLoadError."""
        invalid_source = FakeDataSource(data='{"invalid": json}')

        with pytest.raises(DataLoadError):
            empty_service.load_from_data_source(invalid_source)

    def test_service_usable_after_failed_load(self, empty_service: Service):
        """Service should still be usable after a failed JSON load."""
        invalid_source = FakeDataSource(data='{"invalid": json}')

        try:
            empty_service.load_from_data_source(invalid_source)
        except DataLoadError:
            pass

        # Service should have no data
        assert empty_service.get_employee_by_uid("test") is None


class TestHealthCheck:
    """Tests for health check methods."""

    def test_is_healthy_without_data(self, empty_service: Service):
        """Service should not be healthy without data."""
        assert empty_service.is_healthy() is False

    def test_is_healthy_with_data(self, service: Service):
        """Service should be healthy with data loaded."""
        assert service.is_healthy() is True

    def test_is_ready_without_data(self, empty_service: Service):
        """Service should not be ready without data."""
        assert empty_service.is_ready() is False

    def test_is_ready_with_data(self, service: Service):
        """Service should be ready with data loaded."""
        assert service.is_ready() is True


class TestPIIFreeData:
    """Tests for PII-free data loading and behavior."""

    def test_load_pii_free_data(self, pii_free_data_path: Path):
        """Loading PII-free data should succeed without validation errors."""
        service = Service()
        file_source = FileDataSource(str(pii_free_data_path))
        service.load_from_data_source(file_source)

        version = service.get_version()
        assert version.employee_count == 0
        assert version.org_count == 2

    def test_is_healthy_with_pii_free_data(self, pii_free_service: Service):
        """Service should be healthy with PII-free data loaded."""
        assert pii_free_service.is_healthy() is True

    def test_is_ready_with_pii_free_data(self, pii_free_service: Service):
        """Service should be ready with PII-free data loaded."""
        assert pii_free_service.is_ready() is True

    def test_team_queries_work(self, pii_free_service: Service):
        """Team queries should work with PII-free data."""
        team = pii_free_service.get_team_by_name("test-team")
        assert team is not None
        assert team.name == "test-team"

    def test_employee_queries_return_none(self, pii_free_service: Service):
        """Employee queries should return None with PII-free data."""
        assert pii_free_service.get_employee_by_uid("jsmith") is None

    def test_org_queries_work(self, pii_free_service: Service):
        """Org queries should work with PII-free data."""
        org = pii_free_service.get_org_by_name("test-org")
        assert org is not None
        assert org.name == "test-org"

    def test_rejects_pii_free_with_employees(self):
        """Should reject data claiming pii_free but containing employees."""
        import json

        data = {
            "metadata": {"pii_free": True},
            "lookups": {
                "employees": {"uid1": {"uid": "uid1", "full_name": "Test"}},
                "teams": {},
            },
            "indexes": {"membership": {"membership_index": {}}},
        }
        source = FakeDataSource(data=json.dumps(data))
        service = Service()
        with pytest.raises(DataLoadError, match="pii_free is set but lookups.employees is not empty"):
            service.load_from_data_source(source)

    def test_rejects_pii_free_with_membership(self):
        """Should reject data claiming pii_free but containing membership data."""
        import json

        data = {
            "metadata": {"pii_free": True},
            "lookups": {"employees": {}, "teams": {}},
            "indexes": {
                "membership": {
                    "membership_index": {
                        "uid1": [{"name": "team1", "type": "team"}]
                    }
                }
            },
        }
        source = FakeDataSource(data=json.dumps(data))
        service = Service()
        with pytest.raises(DataLoadError, match="pii_free is set but membership_index is not empty"):
            service.load_from_data_source(source)
