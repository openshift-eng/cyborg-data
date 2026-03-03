"""Tests for the RedactingDataSource wrapper."""

import json
from io import BytesIO

import pytest

from orgdatacore import PIIMode, RedactingDataSource, Service


class FakeDataSource:
    """Fake data source for testing."""

    def __init__(self, data: dict):
        self._data = data

    def load(self) -> BytesIO:
        return BytesIO(json.dumps(self._data).encode("utf-8"))

    def watch(self, callback) -> None:
        return None

    def __str__(self) -> str:
        return "FakeDataSource(in-memory)"


@pytest.fixture
def sample_employee_data() -> dict:
    """Sample data with employee PII fields."""
    return {
        "metadata": {"generated_at": "2025-01-01T10:00:00Z"},
        "lookups": {
            "employees": {
                "jsmith": {
                    "uid": "jsmith",
                    "full_name": "John Smith",
                    "email": "jsmith@example.com",
                    "job_title": "Senior Engineer",
                    "slack_uid": "U12345678",
                    "github_id": "jsmith-gh",
                    "manager_uid": "adoe",
                    "is_people_manager": False,
                },
                "adoe": {
                    "uid": "adoe",
                    "full_name": "Alice Doe",
                    "email": "adoe@example.com",
                    "job_title": "Team Lead",
                    "slack_uid": "U87654321",
                    "github_id": "adoe-gh",
                    "manager_uid": "",
                    "is_people_manager": True,
                },
            },
            "teams": {},
            "orgs": {},
        },
        "indexes": {
            "membership": {
                "membership_index": {
                    "jsmith": [],
                    "adoe": [],
                },
            },
            "slack_id_mappings": {
                "slack_uid_to_uid": {
                    "U12345678": "jsmith",
                    "U87654321": "adoe",
                },
            },
            "github_id_mappings": {
                "github_id_to_uid": {
                    "jsmith-gh": "jsmith",
                    "adoe-gh": "adoe",
                },
            },
        },
    }


class TestRedactingDataSourceFullMode:
    """Tests for FULL PII mode (pass-through)."""

    def test_full_mode_returns_unchanged_data(
        self, sample_employee_data: dict
    ) -> None:
        """In FULL mode, data should pass through unchanged."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.FULL)

        result = json.load(source.load())

        # Verify PII fields are preserved
        jsmith = result["lookups"]["employees"]["jsmith"]
        assert jsmith["full_name"] == "John Smith"
        assert jsmith["email"] == "jsmith@example.com"
        assert jsmith["slack_uid"] == "U12345678"
        assert jsmith["github_id"] == "jsmith-gh"

    def test_full_mode_preserves_indexes(self, sample_employee_data: dict) -> None:
        """Indexes should be preserved in full mode."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.FULL)

        result = json.load(source.load())

        slack_index = result["indexes"]["slack_id_mappings"]["slack_uid_to_uid"]
        assert len(slack_index) > 0
        assert "U12345678" in slack_index

    def test_full_mode_is_default(self, sample_employee_data: dict) -> None:
        """FULL mode should be the default when no pii_mode is specified."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner)  # No pii_mode argument

        result = json.load(source.load())

        jsmith = result["lookups"]["employees"]["jsmith"]
        assert jsmith["full_name"] == "John Smith"


class TestRedactingDataSourceRedactedMode:
    """Tests for REDACTED PII mode."""

    def test_redacted_mode_strips_full_name(
        self, sample_employee_data: dict
    ) -> None:
        """full_name should be replaced with [REDACTED]."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"]["jsmith"]["full_name"] == "[REDACTED]"
        assert result["lookups"]["employees"]["adoe"]["full_name"] == "[REDACTED]"

    def test_redacted_mode_strips_email(self, sample_employee_data: dict) -> None:
        """email should be replaced with [REDACTED]."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"]["jsmith"]["email"] == "[REDACTED]"
        assert result["lookups"]["employees"]["adoe"]["email"] == "[REDACTED]"

    def test_redacted_mode_clears_slack_uid(
        self, sample_employee_data: dict
    ) -> None:
        """slack_uid should be cleared (omitted from JSON)."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"]["jsmith"].get("slack_uid") is None
        assert result["lookups"]["employees"]["adoe"].get("slack_uid") is None

    def test_redacted_mode_clears_github_id(
        self, sample_employee_data: dict
    ) -> None:
        """github_id should be cleared (omitted from JSON)."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"]["jsmith"].get("github_id") is None
        assert result["lookups"]["employees"]["adoe"].get("github_id") is None

    def test_redacted_mode_preserves_non_pii_fields(
        self, sample_employee_data: dict
    ) -> None:
        """Non-PII fields should be preserved."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        jsmith = result["lookups"]["employees"]["jsmith"]
        assert jsmith["uid"] == "jsmith"
        assert jsmith["job_title"] == "Senior Engineer"
        assert jsmith["manager_uid"] == "adoe"

    def test_redacted_mode_preserves_metadata(
        self, sample_employee_data: dict
    ) -> None:
        """Metadata and other lookups should be preserved."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["metadata"]["generated_at"] == "2025-01-01T10:00:00Z"
        assert "teams" in result["lookups"]
        assert "orgs" in result["lookups"]


class TestRedactingDataSourceIndexes:
    """Tests for PII index clearing."""

    def test_redacted_mode_clears_slack_index(
        self, sample_employee_data: dict
    ) -> None:
        """slack_uid_to_uid index should be cleared in redacted mode."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        slack_index = result["indexes"]["slack_id_mappings"]["slack_uid_to_uid"]
        assert slack_index == {}

    def test_redacted_mode_clears_github_index(
        self, sample_employee_data: dict
    ) -> None:
        """github_id_to_uid index should be cleared in redacted mode."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        github_index = result["indexes"]["github_id_mappings"]["github_id_to_uid"]
        assert github_index == {}


class TestRedactingDataSourceEdgeCases:
    """Edge case tests."""

    def test_empty_employees_dict(self) -> None:
        """Should handle empty employees dict."""
        data = {"lookups": {"employees": {}}, "indexes": {"membership": {"membership_index": {}}}}
        inner = FakeDataSource(data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"] == {}

    def test_missing_lookups_key(self) -> None:
        """Should handle missing lookups key."""
        data = {"metadata": {"generated_at": "2025-01-01T10:00:00Z"}}
        inner = FakeDataSource(data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"] == {}

    def test_missing_employees_key(self) -> None:
        """Should handle missing employees key in lookups."""
        data = {"lookups": {"teams": {}}}
        inner = FakeDataSource(data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"] == {}

    def test_missing_indexes_key(self) -> None:
        """Should handle missing indexes key."""
        data = {
            "lookups": {
                "employees": {
                    "jsmith": {
                        "uid": "jsmith",
                        "full_name": "John",
                        "email": "j@x.com",
                        "job_title": "",
                    }
                }
            }
        }
        inner = FakeDataSource(data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        result = json.load(source.load())

        assert result["lookups"]["employees"]["jsmith"]["full_name"] == "[REDACTED]"


class TestRedactingDataSourceStr:
    """Tests for __str__ method."""

    def test_str_full_mode(self, sample_employee_data: dict) -> None:
        """String representation should not show redaction suffix in full mode."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.FULL)

        assert str(source) == "FakeDataSource(in-memory)"

    def test_str_redacted_mode(self, sample_employee_data: dict) -> None:
        """String representation should show redaction suffix in redacted mode."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        assert str(source) == "FakeDataSource(in-memory) [PII redacted]"


class TestRedactingDataSourceWithService:
    """Integration tests with orgdatacore.Service."""

    def test_service_loads_redacted_data(self, sample_employee_data: dict) -> None:
        """Service should load redacted data successfully."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        service = Service()
        service.load_from_data_source(source)

        # Verify service loaded and employee lookups return redacted data
        emp = service.get_employee_by_uid("jsmith")
        assert emp is not None
        assert emp.full_name == "[REDACTED]"
        assert emp.email == "[REDACTED]"
        assert emp.slack_uid == ""

    def test_service_loads_full_data(self, sample_employee_data: dict) -> None:
        """Service should load full data successfully."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.FULL)

        service = Service()
        service.load_from_data_source(source)

        emp = service.get_employee_by_uid("jsmith")
        assert emp is not None
        assert emp.full_name == "John Smith"
        assert emp.email == "jsmith@example.com"

    def test_service_slack_lookup_disabled_in_redacted_mode(
        self, sample_employee_data: dict
    ) -> None:
        """Slack ID lookups should not work in redacted mode."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        service = Service()
        service.load_from_data_source(source)

        # Slack ID lookup should return None since index was cleared
        emp = service.get_employee_by_slack_id("U12345678")
        assert emp is None

    def test_service_github_lookup_disabled_in_redacted_mode(
        self, sample_employee_data: dict
    ) -> None:
        """GitHub ID lookups should not work in redacted mode."""
        inner = FakeDataSource(sample_employee_data)
        source = RedactingDataSource(inner, PIIMode.REDACTED)

        service = Service()
        service.load_from_data_source(source)

        # GitHub ID lookup should return None since index was cleared
        emp = service.get_employee_by_github_id("jsmith-gh")
        assert emp is None
