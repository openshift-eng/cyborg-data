"""Tests for the hierarchy API."""

import pytest

from orgdatacore import Service


class TestHierarchyPathAPI:
    """Tests for get_hierarchy_path API."""

    def test_team_hierarchy_path_not_empty(self, service: Service) -> None:
        """Teams should have a hierarchy path."""
        teams = service.get_all_team_names()
        assert len(teams) > 0, "Expected at least one team"

        team_name = teams[0]
        path = service.get_hierarchy_path(team_name, "team")

        assert len(path) > 0, f"Expected hierarchy path for team {team_name}"
        assert path[0].name == team_name, "First entry should be the team itself"
        assert path[0].type == "team"

    def test_hierarchy_path_ends_at_root(self, service: Service) -> None:
        """Hierarchy path should end at a root org."""
        teams = service.get_all_team_names()
        path = service.get_hierarchy_path(teams[0], "team")
        assert len(path) > 0

        root = path[-1]
        assert root.type == "org", f"Expected root to be org, got {root.type}"

        root_org = service.get_org_by_name(root.name)
        assert root_org is not None
        assert root_org.parent is None, "Root org should have no parent"

    def test_hierarchy_path_types_valid(self, service: Service) -> None:
        """All entries in path should have valid types."""
        valid_types = {"team", "team_group", "pillar", "org"}

        for team_name in service.get_all_team_names():
            path = service.get_hierarchy_path(team_name, "team")
            for entry in path:
                assert entry.type in valid_types, f"Invalid type: {entry.type}"

    def test_hierarchy_path_no_duplicates(self, service: Service) -> None:
        """Hierarchy path should not contain duplicates."""
        for team_name in service.get_all_team_names():
            path = service.get_hierarchy_path(team_name, "team")
            names = [e.name for e in path]
            assert len(names) == len(set(names)), f"Duplicate in path: {names}"

    def test_pillar_hierarchy_path(self, service: Service) -> None:
        """Pillars should have a hierarchy path to root org."""
        pillars = service.get_all_pillar_names()
        if not pillars:
            pytest.skip("No pillars in test data")

        path = service.get_hierarchy_path(pillars[0], "pillar")
        assert len(path) > 0
        assert path[0].type == "pillar"
        assert path[-1].type == "org"

    def test_nonexistent_entity_returns_empty(self, service: Service) -> None:
        """Nonexistent entity should return empty path."""
        path = service.get_hierarchy_path("nonexistent-entity-xyz", "team")
        assert path == []

    def test_invalid_type_returns_empty(self, service: Service) -> None:
        """Invalid entity type should return empty path."""
        teams = service.get_all_team_names()
        path = service.get_hierarchy_path(teams[0], "invalid_type")
        assert path == []


class TestDescendantsTreeAPI:
    """Tests for get_descendants_tree API."""

    def test_root_org_has_descendants(self, service: Service) -> None:
        """Root orgs should have descendants."""
        orgs = service.get_all_org_names()
        assert len(orgs) > 0

        # Find a root org (no parent)
        root_org = None
        for org_name in orgs:
            org = service.get_org_by_name(org_name)
            if org and org.parent is None:
                root_org = org_name
                break

        assert root_org is not None, "Expected at least one root org"

        tree = service.get_descendants_tree(root_org)
        assert tree is not None
        assert tree.name == root_org
        assert tree.type == "org"

    def test_leaf_team_has_no_children(self, service: Service) -> None:
        """Leaf teams should have no children in descendants tree."""
        teams = service.get_all_team_names()

        # Find a leaf team (no children)
        for team_name in teams:
            tree = service.get_descendants_tree(team_name)
            if tree and len(tree.children) == 0:
                assert tree.name == team_name
                return

        pytest.skip("No leaf teams found in test data")

    def test_descendants_tree_structure(self, service: Service) -> None:
        """Descendants tree should have valid structure."""
        from orgdatacore import HierarchyNode

        orgs = service.get_all_org_names()
        tree = service.get_descendants_tree(orgs[0])
        if not tree:
            pytest.skip(f"No tree for {orgs[0]}")

        def validate_node(node: HierarchyNode, visited: set[str] | None = None) -> None:
            if visited is None:
                visited = set()

            assert node.name not in visited, f"Cycle detected at {node.name}"
            visited.add(node.name)

            assert isinstance(node.name, str)
            assert isinstance(node.type, str)
            assert isinstance(node.children, (list, tuple))

            for child in node.children:
                validate_node(child, visited.copy())

        validate_node(tree)

    def test_nonexistent_entity_returns_none(self, service: Service) -> None:
        """Nonexistent entity should return None."""
        tree = service.get_descendants_tree("nonexistent-entity-xyz")
        assert tree is None


class TestHierarchyConsistency:
    """Tests for consistency between hierarchy APIs."""

    def test_parent_child_consistency(self, service: Service) -> None:
        """Parent in hierarchy path should list entity as child in descendants."""
        for team_name in service.get_all_team_names():
            path = service.get_hierarchy_path(team_name, "team")
            if len(path) < 2:
                continue

            parent_entry = path[1]
            parent_tree = service.get_descendants_tree(parent_entry.name)

            if parent_tree:
                child_names = [c.name for c in parent_tree.children]
                assert team_name in child_names, (
                    f"Team {team_name} not in parent {parent_entry.name}'s children"
                )
