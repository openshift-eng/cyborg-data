package orgdatacore

import (
	"testing"
)

func TestHierarchyAPITeamPath(t *testing.T) {
	service := setupTestService(t)

	teams := service.GetAllTeamNames()
	if len(teams) == 0 {
		t.Fatal("Expected at least one team")
	}

	teamName := teams[0]
	path := service.GetHierarchyPath(teamName, "team")

	if len(path) == 0 {
		t.Fatalf("Expected hierarchy path for team %s", teamName)
	}

	if path[0].Name != teamName {
		t.Errorf("First entry should be team itself, got %s", path[0].Name)
	}

	if path[0].Type != "team" {
		t.Errorf("First entry type should be 'team', got %s", path[0].Type)
	}
}

func TestHierarchyAPIPathEndsAtRoot(t *testing.T) {
	service := setupTestService(t)

	teams := service.GetAllTeamNames()
	if len(teams) == 0 {
		t.Skip("No teams in data")
	}

	path := service.GetHierarchyPath(teams[0], "team")
	if len(path) == 0 {
		t.Skip("Empty path")
	}

	root := path[len(path)-1]
	if root.Type != "org" {
		t.Errorf("Expected root to be org, got %s", root.Type)
	}

	rootOrg := service.GetOrgByName(root.Name)
	if rootOrg == nil {
		t.Fatalf("Root org %s not found", root.Name)
	}

	if rootOrg.Parent != nil {
		t.Errorf("Root org should have no parent, got %+v", rootOrg.Parent)
	}
}

func TestHierarchyAPIValidTypes(t *testing.T) {
	service := setupTestService(t)

	validTypes := map[string]bool{
		"team":       true,
		"team_group": true,
		"pillar":     true,
		"org":        true,
	}

	for _, teamName := range service.GetAllTeamNames() {
		path := service.GetHierarchyPath(teamName, "team")
		for _, entry := range path {
			if !validTypes[entry.Type] {
				t.Errorf("Invalid type in path: %s", entry.Type)
			}
		}
	}
}

func TestHierarchyAPINoDuplicates(t *testing.T) {
	service := setupTestService(t)

	for _, teamName := range service.GetAllTeamNames() {
		path := service.GetHierarchyPath(teamName, "team")
		seen := make(map[string]bool)

		for _, entry := range path {
			if seen[entry.Name] {
				t.Errorf("Duplicate in path for %s: %s", teamName, entry.Name)
			}
			seen[entry.Name] = true
		}
	}
}

func TestHierarchyAPIPillarPath(t *testing.T) {
	service := setupTestService(t)

	pillars := service.GetAllPillarNames()
	if len(pillars) == 0 {
		t.Skip("No pillars in test data")
	}

	path := service.GetHierarchyPath(pillars[0], "pillar")
	if len(path) == 0 {
		t.Fatal("Expected hierarchy path for pillar")
	}

	if path[0].Type != "pillar" {
		t.Errorf("First entry should be pillar, got %s", path[0].Type)
	}

	if path[len(path)-1].Type != "org" {
		t.Errorf("Last entry should be org, got %s", path[len(path)-1].Type)
	}
}

func TestHierarchyAPINonexistentEntity(t *testing.T) {
	service := setupTestService(t)

	path := service.GetHierarchyPath("nonexistent-entity-xyz", "team")
	if len(path) != 0 {
		t.Errorf("Expected empty path for nonexistent entity, got %d entries", len(path))
	}
}

func TestHierarchyAPIInvalidType(t *testing.T) {
	service := setupTestService(t)

	teams := service.GetAllTeamNames()
	if len(teams) == 0 {
		t.Skip("No teams in data")
	}

	path := service.GetHierarchyPath(teams[0], "invalid_type")
	if len(path) != 0 {
		t.Errorf("Expected empty path for invalid type, got %d entries", len(path))
	}
}

func TestDescendantsTreeAPIRootOrg(t *testing.T) {
	service := setupTestService(t)

	orgs := service.GetAllOrgNames()
	if len(orgs) == 0 {
		t.Fatal("Expected at least one org")
	}

	// Find root org
	var rootOrg string
	for _, orgName := range orgs {
		org := service.GetOrgByName(orgName)
		if org != nil && org.Parent == nil {
			rootOrg = orgName
			break
		}
	}

	if rootOrg == "" {
		t.Fatal("No root org found")
	}

	tree := service.GetDescendantsTree(rootOrg)
	if tree == nil {
		t.Fatalf("Expected tree for root org %s", rootOrg)
	}

	if tree.Name != rootOrg {
		t.Errorf("Expected tree name %s, got %s", rootOrg, tree.Name)
	}

	if tree.Type != "org" {
		t.Errorf("Expected tree type 'org', got %s", tree.Type)
	}
}

func TestDescendantsTreeAPILeafTeam(t *testing.T) {
	service := setupTestService(t)

	for _, teamName := range service.GetAllTeamNames() {
		tree := service.GetDescendantsTree(teamName)
		if tree != nil && len(tree.Children) == 0 {
			// Found a leaf team
			if tree.Name != teamName {
				t.Errorf("Expected tree name %s, got %s", teamName, tree.Name)
			}
			return
		}
	}

	t.Skip("No leaf teams found in test data")
}

func TestDescendantsTreeAPINonexistent(t *testing.T) {
	service := setupTestService(t)

	tree := service.GetDescendantsTree("nonexistent-entity-xyz")
	if tree != nil {
		t.Error("Expected nil tree for nonexistent entity")
	}
}

func TestHierarchyAPIConsistency(t *testing.T) {
	service := setupTestService(t)

	for _, teamName := range service.GetAllTeamNames() {
		path := service.GetHierarchyPath(teamName, "team")
		if len(path) < 2 {
			continue
		}

		parentEntry := path[1]
		parentTree := service.GetDescendantsTree(parentEntry.Name)
		if parentTree == nil {
			continue
		}

		found := false
		for _, child := range parentTree.Children {
			if child.Name == teamName {
				found = true
				break
			}
		}

		if !found {
			t.Errorf("Team %s not in parent %s's children", teamName, parentEntry.Name)
		}
	}
}
