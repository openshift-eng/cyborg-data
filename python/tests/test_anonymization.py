"""Tests for the AnonymizingDataSource and AsyncAnonymizingDataSource wrappers."""

import json
import re
from io import BytesIO

import pytest

from orgdatacore import (
    AnonymizingDataSource,
    AsyncAnonymizingDataSource,
    AsyncService,
    PIIMode,
    Service,
)

NONCE_PATTERN = re.compile(r"^HUMAN-[a-f0-9]{8}$")
SLACK_NONCE_PATTERN = re.compile(r"^SLACK-[a-f0-9]{8}$")
GITHUB_NONCE_PATTERN = re.compile(r"^GITHUB-[a-f0-9]{8}$")


class FakeDataSource:
    """Fake sync data source for testing."""

    def __init__(self, data: dict):
        self._data = data

    def load(self) -> BytesIO:
        return BytesIO(json.dumps(self._data).encode("utf-8"))

    def watch(self, callback) -> None:
        return None

    def __str__(self) -> str:
        return "FakeDataSource(in-memory)"


class AsyncFakeDataSource:
    """Fake async data source for testing."""

    def __init__(self, data: dict):
        self._data = data

    async def load(self) -> BytesIO:
        return BytesIO(json.dumps(self._data).encode("utf-8"))

    async def watch(self, callback) -> None:
        return None

    def __str__(self) -> str:
        return "AsyncFakeDataSource(in-memory)"


@pytest.fixture
def sample_data() -> dict:
    """Sample org data with employees, groups, and indexes."""
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
            "teams": {
                "test-squad": {
                    "uid": "test-squad",
                    "name": "Test Squad",
                    "tab_name": "test-squad",
                    "description": "A test team",
                    "type": "team",
                    "group": {
                        "resolved_people_uid_list": ["jsmith", "adoe"],
                        "resolved_roles": [
                            {"people": ["adoe"], "roles": ["lead"]},
                        ],
                    },
                },
            },
            "orgs": {
                "test-org": {
                    "uid": "test-org",
                    "name": "Test Org",
                    "tab_name": "test-org",
                    "description": "A test org",
                    "type": "org",
                    "group": {
                        "resolved_people_uid_list": ["jsmith", "adoe"],
                        "resolved_roles": [],
                    },
                },
            },
            "pillars": {},
            "team_groups": {},
        },
        "indexes": {
            "membership": {
                "membership_index": {
                    "jsmith": [{"name": "test-squad", "type": "team"}],
                    "adoe": [{"name": "test-squad", "type": "team"}],
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


class TestAnonymizingDataSourceFullMode:
    """Tests for FULL PII mode (pass-through)."""

    def test_full_mode_returns_unchanged_data(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.FULL)

        result = json.load(source.load())

        jsmith = result["lookups"]["employees"]["jsmith"]
        assert jsmith["full_name"] == "John Smith"
        assert jsmith["email"] == "jsmith@example.com"
        assert jsmith["uid"] == "jsmith"

    def test_full_mode_is_default(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner)

        result = json.load(source.load())

        assert result["lookups"]["employees"]["jsmith"]["full_name"] == "John Smith"


class TestAnonymizingDataSourceAnonymizedMode:
    """Tests for ANONYMIZED PII mode."""

    def test_uids_match_nonce_pattern(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        employees = result["lookups"]["employees"]
        for nonce_key, emp in employees.items():
            assert NONCE_PATTERN.match(nonce_key), f"Key {nonce_key} doesn't match pattern"
            assert NONCE_PATTERN.match(emp["uid"]), f"uid {emp['uid']} doesn't match pattern"
            assert emp["uid"] == nonce_key

    def test_names_anonymized(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        for emp in result["lookups"]["employees"].values():
            assert emp["full_name"] == "[ANONYMIZED]"

    def test_emails_anonymized(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        for emp in result["lookups"]["employees"].values():
            assert emp["email"] == "[ANONYMIZED]"

    def test_slack_uid_anonymized_with_nonce(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        for emp in result["lookups"]["employees"].values():
            assert SLACK_NONCE_PATTERN.match(emp["slack_uid"]), (
                f"slack_uid {emp['slack_uid']!r} doesn't match SLACK nonce pattern"
            )

    def test_github_id_anonymized_with_nonce(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        for emp in result["lookups"]["employees"].values():
            assert GITHUB_NONCE_PATTERN.match(emp["github_id"]), (
                f"github_id {emp['github_id']!r} doesn't match GITHUB nonce pattern"
            )

    def test_manager_uid_consistent(self, sample_data: dict) -> None:
        """Manager UID should use the same nonce as the manager's employee record."""
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        employees = result["lookups"]["employees"]
        # Find the employee whose manager_uid is non-empty
        managed = [e for e in employees.values() if e.get("manager_uid")]
        assert len(managed) == 1

        manager_nonce = managed[0]["manager_uid"]
        assert NONCE_PATTERN.match(manager_nonce)
        # The manager nonce should be a key in the employees dict
        assert manager_nonce in employees

    def test_non_pii_fields_preserved(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        # Job titles should be preserved
        job_titles = {e["job_title"] for e in result["lookups"]["employees"].values()}
        assert "Senior Engineer" in job_titles
        assert "Team Lead" in job_titles

    def test_metadata_preserved(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        assert result["metadata"]["generated_at"] == "2025-01-01T10:00:00Z"


class TestAnonymizingDataSourceIndexes:
    """Tests for index re-keying and clearing."""

    def test_membership_index_rekeyed(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        membership_index = result["indexes"]["membership"]["membership_index"]
        # All keys should be nonces
        for key in membership_index:
            assert NONCE_PATTERN.match(key), f"Membership key {key} not a nonce"
        # Original UIDs should be gone
        assert "jsmith" not in membership_index
        assert "adoe" not in membership_index

    def test_slack_index_remapped_with_nonces(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        slack_index = result["indexes"]["slack_id_mappings"]["slack_uid_to_uid"]
        assert len(slack_index) == 2
        for slack_nonce, uid_nonce in slack_index.items():
            assert SLACK_NONCE_PATTERN.match(slack_nonce), (
                f"slack index key {slack_nonce!r} doesn't match SLACK nonce pattern"
            )
            assert NONCE_PATTERN.match(uid_nonce), (
                f"slack index value {uid_nonce!r} doesn't match HUMAN nonce pattern"
            )
        # Original Slack IDs should be gone
        assert "U12345678" not in slack_index
        assert "U87654321" not in slack_index

    def test_github_index_remapped_with_nonces(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        github_index = result["indexes"]["github_id_mappings"]["github_id_to_uid"]
        assert len(github_index) == 2
        for github_nonce, uid_nonce in github_index.items():
            assert GITHUB_NONCE_PATTERN.match(github_nonce), (
                f"github index key {github_nonce!r} doesn't match GITHUB nonce pattern"
            )
            assert NONCE_PATTERN.match(uid_nonce), (
                f"github index value {uid_nonce!r} doesn't match HUMAN nonce pattern"
            )
        # Original GitHub IDs should be gone
        assert "jsmith-gh" not in github_index
        assert "adoe-gh" not in github_index


class TestAnonymizingDataSourceGroups:
    """Tests for group people list re-mapping."""

    def test_team_resolved_people_remapped(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        people = result["lookups"]["teams"]["test-squad"]["group"]["resolved_people_uid_list"]
        assert len(people) == 2
        for p in people:
            assert NONCE_PATTERN.match(p), f"Person {p} not a nonce"

    def test_org_resolved_people_remapped(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        people = result["lookups"]["orgs"]["test-org"]["group"]["resolved_people_uid_list"]
        assert len(people) == 2
        for p in people:
            assert NONCE_PATTERN.match(p)

    def test_roles_people_remapped(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())

        roles = result["lookups"]["teams"]["test-squad"]["group"]["resolved_roles"]
        assert len(roles) == 1
        for person in roles[0]["people"]:
            assert NONCE_PATTERN.match(person)


class TestAnonymizingDataSourceLookupAPI:
    """Tests for the resolution/lookup API."""

    def test_resolve_returns_real_uid(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()  # Trigger nonce generation

        nonce = source.anonymize_uid("jsmith")
        assert nonce is not None
        assert source.resolve(nonce) == "jsmith"

    def test_anonymize_uid(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()

        nonce = source.anonymize_uid("adoe")
        assert nonce is not None
        assert NONCE_PATTERN.match(nonce)

    def test_lookup_by_name_case_insensitive(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()

        nonce1 = source.lookup_by_name("John Smith")
        nonce2 = source.lookup_by_name("john smith")
        nonce3 = source.lookup_by_name("JOHN SMITH")
        assert nonce1 is not None
        assert nonce1 == nonce2 == nonce3

    def test_get_display_name(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()

        nonce = source.anonymize_uid("jsmith")
        display = source.get_display_name(nonce)
        assert display == "John Smith"

    def test_unknown_nonce_returns_none(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()

        assert source.resolve("HUMAN-00000000") is None
        assert source.get_display_name("HUMAN-00000000") is None

    def test_unknown_uid_returns_none(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()

        assert source.anonymize_uid("nonexistent") is None

    def test_uid_to_nonce_map(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()

        mapping = source.uid_to_nonce_map
        assert "jsmith" in mapping
        assert "adoe" in mapping
        assert len(mapping) == 2

    def test_name_to_nonce_map(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)
        source.load()

        mapping = source.name_to_nonce_map
        assert "john smith" in mapping
        assert "alice doe" in mapping


class TestAnonymizingDataSourceNonceStability:
    """Tests that nonces are stable across reloads for existing UIDs."""

    def test_nonces_stable_between_loads(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        # First load
        source.load()
        nonce1 = source.anonymize_uid("jsmith")

        # Second load — nonces should be preserved for existing UIDs
        source.load()
        nonce2 = source.anonymize_uid("jsmith")

        assert nonce1 is not None
        assert nonce2 is not None
        assert NONCE_PATTERN.match(nonce1)
        assert NONCE_PATTERN.match(nonce2)
        assert nonce1 == nonce2

    def test_new_employee_gets_new_nonce(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        # First load — only jsmith and adoe
        source.load()

        # Add a new employee
        sample_data["lookups"]["employees"]["bnewman"] = {
            "uid": "bnewman",
            "full_name": "Bob Newman",
            "email": "bnewman@example.com",
            "job_title": "Engineer",
            "manager_uid": "adoe",
        }

        # Second load — bnewman should get a fresh nonce
        source.load()
        new_nonce = source.anonymize_uid("bnewman")
        assert new_nonce is not None
        assert NONCE_PATTERN.match(new_nonce)

        # Existing employees keep their nonces
        assert source.anonymize_uid("jsmith") is not None
        assert source.anonymize_uid("adoe") is not None

    def test_removed_employee_nonce_dropped(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        source.load()
        old_nonce = source.anonymize_uid("jsmith")
        assert old_nonce is not None

        # Remove jsmith
        del sample_data["lookups"]["employees"]["jsmith"]
        # Also clean up indexes
        sample_data["indexes"]["membership"]["membership_index"].pop("jsmith", None)

        source.load()
        assert source.anonymize_uid("jsmith") is None
        assert source.resolve(old_nonce) is None


class TestAnonymizingDataSourceStr:
    """Tests for __str__ method."""

    def test_str_full_mode(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.FULL)

        assert str(source) == "FakeDataSource(in-memory)"

    def test_str_anonymized_mode(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        assert str(source) == "FakeDataSource(in-memory) [PII anonymized]"


class TestAnonymizingDataSourceEdgeCases:
    """Edge case tests."""

    def test_empty_employees(self) -> None:
        data = {"lookups": {"employees": {}}, "indexes": {"membership": {"membership_index": {}}}}
        inner = FakeDataSource(data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())
        assert result["lookups"]["employees"] == {}

    def test_missing_lookups(self) -> None:
        data = {"metadata": {"generated_at": "2025-01-01T10:00:00Z"}}
        inner = FakeDataSource(data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())
        assert result["lookups"]["employees"] == {}

    def test_missing_indexes(self) -> None:
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
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(source.load())
        employees = result["lookups"]["employees"]
        assert len(employees) == 1
        emp = list(employees.values())[0]
        assert emp["full_name"] == "[ANONYMIZED]"


class TestAnonymizingDataSourceWithService:
    """Integration tests with orgdatacore.Service."""

    def test_service_loads_anonymized_data(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        service = Service()
        service.load_from_data_source(source)

        # Get the nonce for jsmith
        nonce = source.anonymize_uid("jsmith")
        assert nonce is not None

        emp = service.get_employee_by_uid(nonce)
        assert emp is not None
        assert emp.full_name == "[ANONYMIZED]"
        assert emp.email == "[ANONYMIZED]"
        assert SLACK_NONCE_PATTERN.match(emp.slack_uid)

    def test_service_slack_lookup_works_with_nonce(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        service = Service()
        service.load_from_data_source(source)

        # Original Slack ID should not work
        assert service.get_employee_by_slack_id("U12345678") is None

        # Slack nonce should work
        slack_nonce = source.slack_id_to_nonce_map["U12345678"]
        emp = service.get_employee_by_slack_id(slack_nonce)
        assert emp is not None
        assert emp.full_name == "[ANONYMIZED]"

    def test_service_github_lookup_works_with_nonce(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        service = Service()
        service.load_from_data_source(source)

        # Original GitHub ID should not work
        assert service.get_employee_by_github_id("jsmith-gh") is None

        # GitHub nonce should work
        github_nonce = source.github_id_to_nonce_map["jsmith-gh"]
        emp = service.get_employee_by_github_id(github_nonce)
        assert emp is not None
        assert emp.full_name == "[ANONYMIZED]"

    def test_service_original_uid_not_found(self, sample_data: dict) -> None:
        inner = FakeDataSource(sample_data)
        source = AnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        service = Service()
        service.load_from_data_source(source)

        # Original UID should not be findable
        assert service.get_employee_by_uid("jsmith") is None


class TestAsyncAnonymizingDataSource:
    """Tests for the async variant."""

    @pytest.mark.asyncio
    async def test_async_anonymizes_data(self, sample_data: dict) -> None:
        inner = AsyncFakeDataSource(sample_data)
        source = AsyncAnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        result = json.load(await source.load())

        employees = result["lookups"]["employees"]
        for nonce_key, emp in employees.items():
            assert NONCE_PATTERN.match(nonce_key)
            assert emp["full_name"] == "[ANONYMIZED]"

    @pytest.mark.asyncio
    async def test_async_full_mode_passthrough(self, sample_data: dict) -> None:
        inner = AsyncFakeDataSource(sample_data)
        source = AsyncAnonymizingDataSource(inner, PIIMode.FULL)

        result = json.load(await source.load())

        assert result["lookups"]["employees"]["jsmith"]["full_name"] == "John Smith"

    @pytest.mark.asyncio
    async def test_async_lookup_api(self, sample_data: dict) -> None:
        inner = AsyncFakeDataSource(sample_data)
        source = AsyncAnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        await source.load()

        nonce = source.anonymize_uid("jsmith")
        assert nonce is not None
        assert source.resolve(nonce) == "jsmith"
        assert source.get_display_name(nonce) == "John Smith"

    def test_async_str(self, sample_data: dict) -> None:
        inner = AsyncFakeDataSource(sample_data)
        source = AsyncAnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        assert str(source) == "AsyncFakeDataSource(in-memory) [PII anonymized]"

    @pytest.mark.asyncio
    async def test_async_with_service(self, sample_data: dict) -> None:
        inner = AsyncFakeDataSource(sample_data)
        source = AsyncAnonymizingDataSource(inner, PIIMode.ANONYMIZED)

        service = AsyncService(data_source=source)
        await service.initialize()

        nonce = source.anonymize_uid("jsmith")
        emp = await service.get_employee_by_uid(nonce)
        assert emp is not None
        assert emp.full_name == "[ANONYMIZED]"
