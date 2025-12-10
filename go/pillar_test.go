package orgdatacore

import (
	"testing"
)

func TestGetPillarByName(t *testing.T) {
	service := NewService()
	service.data = &Data{
		Lookups: Lookups{
			Pillars: map[string]Pillar{
				"Engineering": {
					UID:  "pillar1",
					Name: "Engineering",
					Type: "pillar",
					Group: Group{
						Type: GroupType{
							Name: "pillar",
						},
						ResolvedPeopleUIDList: []string{"user1", "user2"},
					},
				},
			},
		},
	}

	tests := []struct {
		name        string
		pillarName  string
		expectNil   bool
		expectedUID string
	}{
		{
			name:        "existing pillar",
			pillarName:  "Engineering",
			expectNil:   false,
			expectedUID: "pillar1",
		},
		{
			name:       "nonexistent pillar",
			pillarName: "Nonexistent",
			expectNil:  true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetPillarByName(tt.pillarName)
			if tt.expectNil {
				if result != nil {
					t.Errorf("expected nil, got %+v", result)
				}
			} else {
				if result == nil {
					t.Errorf("expected pillar, got nil")
				} else if result.UID != tt.expectedUID {
					t.Errorf("expected UID %s, got %s", tt.expectedUID, result.UID)
				}
			}
		})
	}
}

func TestGetAllPillarNames(t *testing.T) {
	service := NewService()
	service.data = &Data{
		Lookups: Lookups{
			Pillars: map[string]Pillar{
				"Engineering": {
					UID:  "pillar1",
					Name: "Engineering",
				},
				"Product": {
					UID:  "pillar2",
					Name: "Product",
				},
			},
		},
	}

	names := service.GetAllPillarNames()
	if len(names) != 2 {
		t.Errorf("expected 2 pillar names, got %d", len(names))
	}

	// Check both names are present (order doesn't matter)
	found := make(map[string]bool)
	for _, name := range names {
		found[name] = true
	}

	if !found["Engineering"] || !found["Product"] {
		t.Errorf("expected to find Engineering and Product, got %v", names)
	}
}
