"""Tests for team group-related functionality."""

import pytest

from orgdatacore import Service
from orgdatacore.types import (
    Data, Lookups, Indexes, TeamGroup, Group, GroupType,
    MembershipIndex, SlackIDMappings, GitHubIDMappings,
)


class TestGetTeamGroupByName:
    """Tests for team group lookup by name."""

    def test_get_existing_team_group(self):
        """Test that an existing team group can be retrieved."""
        service = Service()
        service._data = Data(
            lookups=Lookups(
                team_groups={
                    "Platform Teams": TeamGroup(
                        uid="tg1",
                        name="Platform Teams",
                        type="team_group",
                        group=Group(
                            type=GroupType(name="team_group"),
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

        result = service.get_team_group_by_name("Platform Teams")
        assert result is not None
        assert result.uid == "tg1"

    def test_get_nonexistent_team_group(self):
        """Test that getting a nonexistent team group returns None."""
        service = Service()
        service._data = Data(
            lookups=Lookups(
                team_groups={
                    "Platform Teams": TeamGroup(
                        uid="tg1",
                        name="Platform Teams",
                        type="team_group",
                        group=Group(
                            type=GroupType(name="team_group"),
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

        result = service.get_team_group_by_name("Nonexistent")
        assert result is None


class TestGetAllTeamGroupNames:
    """Tests for getting all team group names."""

    def test_get_all_team_group_names(self):
        """Test that all team group names are returned."""
        service = Service()
        service._data = Data(
            lookups=Lookups(
                team_groups={
                    "Platform Teams": TeamGroup(
                        uid="tg1",
                        name="Platform Teams",
                    ),
                    "Product Teams": TeamGroup(
                        uid="tg2",
                        name="Product Teams",
                    ),
                },
            ),
            indexes=Indexes(
                membership=MembershipIndex(),
                slack_id_mappings=SlackIDMappings(),
                github_id_mappings=GitHubIDMappings(),
            ),
        )

        names = service.get_all_team_group_names()
        assert len(names) == 2
        assert "Platform Teams" in names
        assert "Product Teams" in names

