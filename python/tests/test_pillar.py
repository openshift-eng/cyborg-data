"""Tests for pillar-related functionality."""

import pytest

from orgdatacore import Service
from orgdatacore import (
    Data, Lookups, Indexes, Pillar, Group, GroupType,
    MembershipIndex, SlackIDMappings, GitHubIDMappings,
)


class TestGetPillarByName:
    """Tests for pillar lookup by name."""

    def test_get_existing_pillar(self):
        """Test that an existing pillar can be retrieved."""
        service = Service()
        service._data = Data(
            lookups=Lookups(
                pillars={
                    "Engineering": Pillar(
                        uid="pillar1",
                        name="Engineering",
                        type="pillar",
                        group=Group(
                            type=GroupType(name="pillar"),
                            resolved_people_uid_list=["user1", "user2"],
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

        result = service.get_pillar_by_name("Engineering")
        assert result is not None
        assert result.uid == "pillar1"

    def test_get_nonexistent_pillar(self):
        """Test that getting a nonexistent pillar returns None."""
        service = Service()
        service._data = Data(
            lookups=Lookups(
                pillars={
                    "Engineering": Pillar(
                        uid="pillar1",
                        name="Engineering",
                        type="pillar",
                        group=Group(
                            type=GroupType(name="pillar"),
                            resolved_people_uid_list=["user1", "user2"],
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

        result = service.get_pillar_by_name("Nonexistent")
        assert result is None


class TestGetAllPillarNames:
    """Tests for getting all pillar names."""

    def test_get_all_pillar_names(self):
        """Test that all pillar names are returned."""
        service = Service()
        service._data = Data(
            lookups=Lookups(
                pillars={
                    "Engineering": Pillar(
                        uid="pillar1",
                        name="Engineering",
                    ),
                    "Product": Pillar(
                        uid="pillar2",
                        name="Product",
                    ),
                },
            ),
            indexes=Indexes(
                membership=MembershipIndex(),
                slack_id_mappings=SlackIDMappings(),
                github_id_mappings=GitHubIDMappings(),
            ),
        )

        names = service.get_all_pillar_names()
        assert len(names) == 2
        assert "Engineering" in names
        assert "Product" in names


