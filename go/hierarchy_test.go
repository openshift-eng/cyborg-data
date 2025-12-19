package orgdatacore

import (
	"testing"
)

func TestGetHierarchyPath(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name           string
		entityName     string
		entityType     string
		expectedLength int
		expectedFirst  HierarchyPathEntry
		expectedLast   HierarchyPathEntry
	}{
		{
			name:           "team hierarchy path",
			entityName:     "test-team",
			entityType:     "team",
			expectedLength: 2,
			expectedFirst:  HierarchyPathEntry{Name: "test-team", Type: "team"},
			expectedLast:   HierarchyPathEntry{Name: "test-org", Type: "org"},
		},
		{
			name:           "deeply nested team hierarchy path",
			entityName:     "platform-team",
			entityType:     "team",
			expectedLength: 5,
			expectedFirst:  HierarchyPathEntry{Name: "platform-team", Type: "team"},
			expectedLast:   HierarchyPathEntry{Name: "test-org", Type: "org"},
		},
		{
			name:           "org hierarchy path",
			entityName:     "platform-org",
			entityType:     "org",
			expectedLength: 2,
			expectedFirst:  HierarchyPathEntry{Name: "platform-org", Type: "org"},
			expectedLast:   HierarchyPathEntry{Name: "test-org", Type: "org"},
		},
		{
			name:           "root org hierarchy path",
			entityName:     "test-org",
			entityType:     "org",
			expectedLength: 1,
			expectedFirst:  HierarchyPathEntry{Name: "test-org", Type: "org"},
			expectedLast:   HierarchyPathEntry{Name: "test-org", Type: "org"},
		},
		{
			name:           "pillar hierarchy path",
			entityName:     "engineering",
			entityType:     "pillar",
			expectedLength: 3,
			expectedFirst:  HierarchyPathEntry{Name: "engineering", Type: "pillar"},
			expectedLast:   HierarchyPathEntry{Name: "test-org", Type: "org"},
		},
		{
			name:           "team_group hierarchy path",
			entityName:     "backend-teams",
			entityType:     "team_group",
			expectedLength: 4,
			expectedFirst:  HierarchyPathEntry{Name: "backend-teams", Type: "team_group"},
			expectedLast:   HierarchyPathEntry{Name: "test-org", Type: "org"},
		},
		{
			name:           "nonexistent entity",
			entityName:     "nonexistent",
			entityType:     "team",
			expectedLength: 0,
		},
		{
			name:           "invalid type",
			entityName:     "test-team",
			entityType:     "invalid_type",
			expectedLength: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := service.GetHierarchyPath(tt.entityName, tt.entityType)

			if len(path) != tt.expectedLength {
				t.Errorf("Expected path length %d, got %d", tt.expectedLength, len(path))
				return
			}

			if tt.expectedLength > 0 {
				if path[0].Name != tt.expectedFirst.Name || path[0].Type != tt.expectedFirst.Type {
					t.Errorf("Expected first entry %+v, got %+v", tt.expectedFirst, path[0])
				}
				if path[len(path)-1].Name != tt.expectedLast.Name || path[len(path)-1].Type != tt.expectedLast.Type {
					t.Errorf("Expected last entry %+v, got %+v", tt.expectedLast, path[len(path)-1])
				}
			}
		})
	}
}

func TestGetHierarchyPathDeepTeamDetails(t *testing.T) {
	service := setupTestService(t)

	path := service.GetHierarchyPath("platform-team", "team")

	expected := []HierarchyPathEntry{
		{Name: "platform-team", Type: "team"},
		{Name: "backend-teams", Type: "team_group"},
		{Name: "engineering", Type: "pillar"},
		{Name: "platform-org", Type: "org"},
		{Name: "test-org", Type: "org"},
	}

	if len(path) != len(expected) {
		t.Fatalf("Expected %d entries, got %d", len(expected), len(path))
	}

	for i, exp := range expected {
		if path[i].Name != exp.Name || path[i].Type != exp.Type {
			t.Errorf("Entry %d: expected %+v, got %+v", i, exp, path[i])
		}
	}
}

func TestGetHierarchyPathNoData(t *testing.T) {
	service := NewService()

	path := service.GetHierarchyPath("test-team", "team")
	if len(path) != 0 {
		t.Errorf("Expected empty path when no data loaded, got %d entries", len(path))
	}
}

func TestGetDescendantsTree(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name             string
		entityName       string
		expectedNotNil   bool
		expectedType     string
		expectedChildren int
	}{
		{
			name:             "root org tree",
			entityName:       "test-org",
			expectedNotNil:   true,
			expectedType:     "org",
			expectedChildren: 2, // test-team and platform-org
		},
		{
			name:             "nested org tree",
			entityName:       "platform-org",
			expectedNotNil:   true,
			expectedType:     "org",
			expectedChildren: 1, // engineering
		},
		{
			name:             "pillar tree",
			entityName:       "engineering",
			expectedNotNil:   true,
			expectedType:     "pillar",
			expectedChildren: 1, // backend-teams
		},
		{
			name:             "team_group tree",
			entityName:       "backend-teams",
			expectedNotNil:   true,
			expectedType:     "team_group",
			expectedChildren: 1, // platform-team
		},
		{
			name:             "leaf team tree",
			entityName:       "test-team",
			expectedNotNil:   true,
			expectedType:     "team",
			expectedChildren: 0,
		},
		{
			name:           "nonexistent entity",
			entityName:     "nonexistent",
			expectedNotNil: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tree := service.GetDescendantsTree(tt.entityName)

			if tt.expectedNotNil {
				if tree == nil {
					t.Fatal("Expected non-nil tree")
				}
				if tree.Name != tt.entityName {
					t.Errorf("Expected name %q, got %q", tt.entityName, tree.Name)
				}
				if tree.Type != tt.expectedType {
					t.Errorf("Expected type %q, got %q", tt.expectedType, tree.Type)
				}
				if len(tree.Children) != tt.expectedChildren {
					t.Errorf("Expected %d children, got %d", tt.expectedChildren, len(tree.Children))
				}
			} else {
				if tree != nil {
					t.Error("Expected nil tree for nonexistent entity")
				}
			}
		})
	}
}

func TestGetDescendantsTreeFullHierarchy(t *testing.T) {
	service := setupTestService(t)

	tree := service.GetDescendantsTree("test-org")
	if tree == nil {
		t.Fatal("Expected non-nil tree for test-org")
	}

	// Find platform-org in children
	var platformOrg *HierarchyNode
	for i := range tree.Children {
		if tree.Children[i].Name == "platform-org" {
			platformOrg = &tree.Children[i]
			break
		}
	}
	if platformOrg == nil {
		t.Fatal("Expected to find platform-org in children")
	}

	// Navigate to platform-team
	if len(platformOrg.Children) != 1 || platformOrg.Children[0].Name != "engineering" {
		t.Fatalf("Expected engineering as child of platform-org")
	}

	engineering := &platformOrg.Children[0]
	if len(engineering.Children) != 1 || engineering.Children[0].Name != "backend-teams" {
		t.Fatalf("Expected backend-teams as child of engineering")
	}

	backend := &engineering.Children[0]
	if len(backend.Children) != 1 || backend.Children[0].Name != "platform-team" {
		t.Fatalf("Expected platform-team as child of backend-teams")
	}

	platformTeam := &backend.Children[0]
	if len(platformTeam.Children) != 0 {
		t.Error("Expected platform-team to have no children (leaf node)")
	}
}

func TestGetDescendantsTreeNoData(t *testing.T) {
	service := NewService()

	tree := service.GetDescendantsTree("test-org")
	if tree != nil {
		t.Error("Expected nil tree when no data loaded")
	}
}
