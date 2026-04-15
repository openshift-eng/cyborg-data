"""Tests for context query methods."""

import pytest
from orgdatacore import ContextItemInfo, Service


class TestGetContextForTeam:
    """Tests for get_context_for_team."""

    def test_returns_resolved_context(self, service: Service):
        result = service.get_context_for_team("platform-team")
        assert len(result) == 3
        assert all(isinstance(item, ContextItemInfo) for item in result)

    def test_includes_inherited_items(self, service: Service):
        result = service.get_context_for_team("platform-team")
        source_entities = [item.source_entity for item in result]
        assert "test-org" in source_entities
        assert "platform-team" in source_entities

    def test_superseded_items_not_present(self, service: Service):
        result = service.get_context_for_team("platform-team")
        release_items = [item for item in result if "release_framework" in item.types]
        assert len(release_items) == 1
        assert release_items[0].source_entity == "platform-team"

    def test_returns_empty_for_team_without_context(self, service: Service):
        result = service.get_context_for_team("test-team")
        assert result == []

    def test_returns_empty_for_nonexistent_team(self, service: Service):
        result = service.get_context_for_team("nonexistent")
        assert result == []

    def test_returns_empty_for_empty_string(self, service: Service):
        result = service.get_context_for_team("")
        assert result == []

    def test_context_item_fields(self, service: Service):
        result = service.get_context_for_team("platform-team")
        onboarding = [item for item in result if "team_onboarding" in item.types]
        assert len(onboarding) == 1
        item = onboarding[0]
        assert item.name == "Platform Onboarding Guide"
        assert item.description == "Getting started with the platform team"
        assert item.url == "https://docs.example.com/platform/onboarding"
        assert item.inheritance == "additive"
        assert item.source_entity == "platform-team"
        assert item.source_type == "team"


class TestGetContextForEntity:
    """Tests for get_context_for_entity."""

    def test_returns_context_for_org(self, service: Service):
        result = service.get_context_for_entity("test-org", "org")
        assert len(result) == 2

    def test_returns_context_for_team(self, service: Service):
        result = service.get_context_for_entity("platform-team", "team")
        assert len(result) == 3

    def test_returns_empty_for_entity_without_context(self, service: Service):
        result = service.get_context_for_entity("backend-teams", "team_group")
        assert result == []

    def test_returns_empty_for_nonexistent_entity(self, service: Service):
        result = service.get_context_for_entity("nonexistent", "team")
        assert result == []

    def test_returns_empty_for_empty_name(self, service: Service):
        result = service.get_context_for_entity("", "team")
        assert result == []


class TestGetContextByType:
    """Tests for get_context_by_type."""

    def test_filters_by_context_type(self, service: Service):
        result = service.get_context_by_type("platform-team", "team_onboarding", "team")
        assert len(result) == 1
        assert result[0].name == "Platform Onboarding Guide"

    def test_returns_inherited_matching_type(self, service: Service):
        result = service.get_context_by_type("platform-team", "code_review_standards", "team")
        assert len(result) == 1
        assert result[0].source_entity == "test-org"

    def test_returns_empty_for_unmatched_type(self, service: Service):
        result = service.get_context_by_type("platform-team", "security_guidelines", "team")
        assert result == []

    def test_returns_empty_for_nonexistent_entity(self, service: Service):
        result = service.get_context_by_type("nonexistent", "team_onboarding", "team")
        assert result == []


class TestGetAllContextTypesForEntity:
    """Tests for get_all_context_types_for_entity."""

    def test_returns_distinct_types(self, service: Service):
        result = service.get_all_context_types_for_entity("platform-team", "team")
        assert set(result) == {"code_review_standards", "team_onboarding", "release_framework"}

    def test_returns_types_for_org(self, service: Service):
        result = service.get_all_context_types_for_entity("test-org", "org")
        assert set(result) == {"release_framework", "code_review_standards"}

    def test_returns_empty_for_entity_without_context(self, service: Service):
        result = service.get_all_context_types_for_entity("backend-teams", "team_group")
        assert result == []

    def test_returns_empty_for_nonexistent_entity(self, service: Service):
        result = service.get_all_context_types_for_entity("nonexistent", "team")
        assert result == []


class TestGetContextTypeDescriptions:
    """Tests for get_context_type_descriptions."""

    def test_returns_descriptions_dict(self, service: Service):
        result = service.get_context_type_descriptions()
        assert isinstance(result, dict)
        assert len(result) == 4

    def test_contains_expected_types(self, service: Service):
        result = service.get_context_type_descriptions()
        assert "team_overview" in result
        assert "release_framework" in result
        assert "code_review_standards" in result
        assert "team_onboarding" in result

    def test_descriptions_are_non_empty(self, service: Service):
        result = service.get_context_type_descriptions()
        for desc in result.values():
            assert desc != ""

    def test_returns_empty_for_empty_service(self):
        svc = Service()
        result = svc.get_context_type_descriptions()
        assert result == {}
