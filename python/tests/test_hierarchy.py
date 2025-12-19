"""Tests for hierarchy traversal methods."""

from orgdatacore import HierarchyPathEntry, Service


class TestGetHierarchyPath:
    """Tests for get_hierarchy_path method."""

    def test_get_hierarchy_path_for_team(self, service: Service) -> None:
        """Test getting hierarchy path for a team."""
        path = service.get_hierarchy_path("test-team", "team")
        assert len(path) == 2
        assert path[0].name == "test-team"
        assert path[0].type == "team"
        assert path[1].name == "test-org"
        assert path[1].type == "org"

    def test_get_hierarchy_path_for_deep_team(self, service: Service) -> None:
        """Test getting hierarchy path for a deeply nested team."""
        path = service.get_hierarchy_path("platform-team", "team")
        assert len(path) == 5
        assert path[0].name == "platform-team"
        assert path[0].type == "team"
        assert path[1].name == "backend-teams"
        assert path[1].type == "team_group"
        assert path[2].name == "engineering"
        assert path[2].type == "pillar"
        assert path[3].name == "platform-org"
        assert path[3].type == "org"
        assert path[4].name == "test-org"
        assert path[4].type == "org"

    def test_get_hierarchy_path_for_org(self, service: Service) -> None:
        """Test getting hierarchy path for an org."""
        path = service.get_hierarchy_path("platform-org", "org")
        assert len(path) == 2
        assert path[0].name == "platform-org"
        assert path[0].type == "org"
        assert path[1].name == "test-org"
        assert path[1].type == "org"

    def test_get_hierarchy_path_for_root_org(self, service: Service) -> None:
        """Test getting hierarchy path for root org."""
        path = service.get_hierarchy_path("test-org", "org")
        assert len(path) == 1
        assert path[0].name == "test-org"
        assert path[0].type == "org"

    def test_get_hierarchy_path_for_pillar(self, service: Service) -> None:
        """Test getting hierarchy path for a pillar."""
        path = service.get_hierarchy_path("engineering", "pillar")
        assert len(path) == 3
        assert path[0].name == "engineering"
        assert path[0].type == "pillar"
        assert path[1].name == "platform-org"
        assert path[1].type == "org"
        assert path[2].name == "test-org"
        assert path[2].type == "org"

    def test_get_hierarchy_path_for_team_group(self, service: Service) -> None:
        """Test getting hierarchy path for a team group."""
        path = service.get_hierarchy_path("backend-teams", "team_group")
        assert len(path) == 4
        assert path[0].name == "backend-teams"
        assert path[0].type == "team_group"
        assert path[1].name == "engineering"
        assert path[1].type == "pillar"
        assert path[2].name == "platform-org"
        assert path[2].type == "org"
        assert path[3].name == "test-org"
        assert path[3].type == "org"

    def test_get_hierarchy_path_nonexistent_entity(self, service: Service) -> None:
        """Test getting hierarchy path for nonexistent entity returns empty list."""
        path = service.get_hierarchy_path("nonexistent", "team")
        assert path == []

    def test_get_hierarchy_path_invalid_type(self, service: Service) -> None:
        """Test getting hierarchy path with invalid type returns empty list."""
        path = service.get_hierarchy_path("test-team", "invalid_type")
        assert path == []

    def test_get_hierarchy_path_returns_hierarchy_path_entries(self, service: Service) -> None:
        """Test that returned items are HierarchyPathEntry objects."""
        path = service.get_hierarchy_path("test-team", "team")
        assert all(isinstance(entry, HierarchyPathEntry) for entry in path)

    def test_get_hierarchy_path_no_data(self, empty_service: Service) -> None:
        """Test get_hierarchy_path returns empty list when no data loaded."""
        path = empty_service.get_hierarchy_path("test-team", "team")
        assert path == []


class TestGetDescendantsTree:
    """Tests for get_descendants_tree method."""

    def test_get_descendants_tree_for_root_org(self, service: Service) -> None:
        """Test getting descendants tree for root org."""
        tree = service.get_descendants_tree("test-org")
        assert tree is not None
        assert tree.name == "test-org"
        assert tree.type == "org"
        assert len(tree.children) == 2  # test-team and platform-org

    def test_get_descendants_tree_for_nested_org(self, service: Service) -> None:
        """Test getting descendants tree for nested org."""
        tree = service.get_descendants_tree("platform-org")
        assert tree is not None
        assert tree.name == "platform-org"
        assert tree.type == "org"
        assert len(tree.children) == 1  # engineering

        engineering = tree.children[0]
        assert engineering.name == "engineering"
        assert engineering.type == "pillar"

    def test_get_descendants_tree_for_pillar(self, service: Service) -> None:
        """Test getting descendants tree for pillar."""
        tree = service.get_descendants_tree("engineering")
        assert tree is not None
        assert tree.name == "engineering"
        assert tree.type == "pillar"
        assert len(tree.children) == 1  # backend-teams

        backend = tree.children[0]
        assert backend.name == "backend-teams"
        assert backend.type == "team_group"

    def test_get_descendants_tree_for_team_group(self, service: Service) -> None:
        """Test getting descendants tree for team group."""
        tree = service.get_descendants_tree("backend-teams")
        assert tree is not None
        assert tree.name == "backend-teams"
        assert tree.type == "team_group"
        assert len(tree.children) == 1  # platform-team

        platform = tree.children[0]
        assert platform.name == "platform-team"
        assert platform.type == "team"
        assert len(platform.children) == 0  # leaf node

    def test_get_descendants_tree_for_leaf_team(self, service: Service) -> None:
        """Test getting descendants tree for leaf team (no children)."""
        tree = service.get_descendants_tree("test-team")
        assert tree is not None
        assert tree.name == "test-team"
        assert tree.type == "team"
        assert len(tree.children) == 0

    def test_get_descendants_tree_nonexistent_entity(self, service: Service) -> None:
        """Test getting descendants tree for nonexistent entity returns None."""
        tree = service.get_descendants_tree("nonexistent")
        assert tree is None

    def test_get_descendants_tree_full_hierarchy(self, service: Service) -> None:
        """Test traversing full hierarchy from root to leaves."""
        tree = service.get_descendants_tree("test-org")
        assert tree is not None

        # Find platform-org in children
        platform_org = next((c for c in tree.children if c.name == "platform-org"), None)
        assert platform_org is not None

        # Navigate to platform-team
        engineering = platform_org.children[0]
        assert engineering.name == "engineering"

        backend = engineering.children[0]
        assert backend.name == "backend-teams"

        platform_team = backend.children[0]
        assert platform_team.name == "platform-team"
        assert len(platform_team.children) == 0

    def test_get_descendants_tree_no_data(self, empty_service: Service) -> None:
        """Test get_descendants_tree returns None when no data loaded."""
        tree = empty_service.get_descendants_tree("test-org")
        assert tree is None
