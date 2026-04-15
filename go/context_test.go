package orgdatacore

import (
	"reflect"
	"sort"
	"testing"
)

func TestGetContextForTeam(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name          string
		teamName      string
		expectedCount int
	}{
		{
			name:          "team with resolved context",
			teamName:      "platform-team",
			expectedCount: 3,
		},
		{
			name:          "team without context",
			teamName:      "test-team",
			expectedCount: 0,
		},
		{
			name:          "nonexistent team",
			teamName:      "nonexistent",
			expectedCount: 0,
		},
		{
			name:          "empty team name",
			teamName:      "",
			expectedCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetContextForTeam(tt.teamName)
			if len(result) != tt.expectedCount {
				t.Errorf("GetContextForTeam(%q) returned %d items, expected %d",
					tt.teamName, len(result), tt.expectedCount)
			}
		})
	}
}

func TestGetContextForTeamFields(t *testing.T) {
	service := setupTestService(t)
	result := service.GetContextForTeam("platform-team")

	// Find the onboarding item
	var onboarding *ContextItemInfo
	for i := range result {
		for _, typ := range result[i].Types {
			if typ == "team_onboarding" {
				onboarding = &result[i]
				break
			}
		}
	}

	if onboarding == nil {
		t.Fatal("expected to find team_onboarding context item")
	}
	if onboarding.Name != "Platform Onboarding Guide" {
		t.Errorf("Name = %q, expected %q", onboarding.Name, "Platform Onboarding Guide")
	}
	if onboarding.Description != "Getting started with the platform team" {
		t.Errorf("Description = %q, expected %q", onboarding.Description, "Getting started with the platform team")
	}
	if onboarding.URL != "https://docs.example.com/platform/onboarding" {
		t.Errorf("URL = %q, expected %q", onboarding.URL, "https://docs.example.com/platform/onboarding")
	}
	if onboarding.Inheritance != "additive" {
		t.Errorf("Inheritance = %q, expected %q", onboarding.Inheritance, "additive")
	}
	if onboarding.SourceEntity != "platform-team" {
		t.Errorf("SourceEntity = %q, expected %q", onboarding.SourceEntity, "platform-team")
	}
	if onboarding.SourceType != "team" {
		t.Errorf("SourceType = %q, expected %q", onboarding.SourceType, "team")
	}
}

func TestGetContextForTeamInheritance(t *testing.T) {
	service := setupTestService(t)
	result := service.GetContextForTeam("platform-team")

	sourceEntities := make(map[string]bool)
	for _, item := range result {
		sourceEntities[item.SourceEntity] = true
	}
	if !sourceEntities["test-org"] {
		t.Error("expected inherited items from test-org")
	}
	if !sourceEntities["platform-team"] {
		t.Error("expected items from platform-team")
	}

	// Superseded: only platform-team's release_framework should be present
	var releaseItems []ContextItemInfo
	for _, item := range result {
		for _, typ := range item.Types {
			if typ == "release_framework" {
				releaseItems = append(releaseItems, item)
				break
			}
		}
	}
	if len(releaseItems) != 1 {
		t.Fatalf("expected 1 release_framework item, got %d", len(releaseItems))
	}
	if releaseItems[0].SourceEntity != "platform-team" {
		t.Errorf("release_framework source = %q, expected platform-team", releaseItems[0].SourceEntity)
	}
}

func TestGetContextForEntity(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name          string
		entityName    string
		entityType    string
		expectedCount int
	}{
		{
			name:          "org with context",
			entityName:    "test-org",
			entityType:    "org",
			expectedCount: 2,
		},
		{
			name:          "team with context",
			entityName:    "platform-team",
			entityType:    "team",
			expectedCount: 3,
		},
		{
			name:          "entity without context",
			entityName:    "backend-teams",
			entityType:    "team_group",
			expectedCount: 0,
		},
		{
			name:          "nonexistent entity",
			entityName:    "nonexistent",
			entityType:    "team",
			expectedCount: 0,
		},
		{
			name:          "empty name",
			entityName:    "",
			entityType:    "team",
			expectedCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetContextForEntity(tt.entityName, tt.entityType)
			if len(result) != tt.expectedCount {
				t.Errorf("GetContextForEntity(%q, %q) returned %d items, expected %d",
					tt.entityName, tt.entityType, len(result), tt.expectedCount)
			}
		})
	}
}

func TestGetContextByType(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name          string
		entityName    string
		contextType   string
		entityType    string
		expectedCount int
	}{
		{
			name:          "matching type",
			entityName:    "platform-team",
			contextType:   "team_onboarding",
			entityType:    "team",
			expectedCount: 1,
		},
		{
			name:          "inherited type",
			entityName:    "platform-team",
			contextType:   "code_review_standards",
			entityType:    "team",
			expectedCount: 1,
		},
		{
			name:          "unmatched type",
			entityName:    "platform-team",
			contextType:   "security_guidelines",
			entityType:    "team",
			expectedCount: 0,
		},
		{
			name:          "nonexistent entity",
			entityName:    "nonexistent",
			contextType:   "team_onboarding",
			entityType:    "team",
			expectedCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetContextByType(tt.entityName, tt.contextType, tt.entityType)
			if len(result) != tt.expectedCount {
				t.Errorf("GetContextByType(%q, %q, %q) returned %d items, expected %d",
					tt.entityName, tt.contextType, tt.entityType, len(result), tt.expectedCount)
			}
		})
	}
}

func TestGetAllContextTypesForEntity(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name          string
		entityName    string
		entityType    string
		expectedTypes []string
	}{
		{
			name:          "team with multiple types",
			entityName:    "platform-team",
			entityType:    "team",
			expectedTypes: []string{"code_review_standards", "release_framework", "team_onboarding"},
		},
		{
			name:          "org with types",
			entityName:    "test-org",
			entityType:    "org",
			expectedTypes: []string{"code_review_standards", "release_framework"},
		},
		{
			name:          "entity without context",
			entityName:    "backend-teams",
			entityType:    "team_group",
			expectedTypes: []string{},
		},
		{
			name:          "nonexistent entity",
			entityName:    "nonexistent",
			entityType:    "team",
			expectedTypes: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetAllContextTypesForEntity(tt.entityName, tt.entityType)
			sort.Strings(result)
			sort.Strings(tt.expectedTypes)
			if !reflect.DeepEqual(result, tt.expectedTypes) {
				t.Errorf("GetAllContextTypesForEntity(%q, %q) = %v, expected %v",
					tt.entityName, tt.entityType, result, tt.expectedTypes)
			}
		})
	}
}

func TestGetContextTypeDescriptions(t *testing.T) {
	service := setupTestService(t)

	result := service.GetContextTypeDescriptions()
	if len(result) != 4 {
		t.Errorf("expected 4 descriptions, got %d", len(result))
	}

	expectedKeys := []string{"team_overview", "release_framework", "code_review_standards", "team_onboarding"}
	for _, key := range expectedKeys {
		if _, ok := result[key]; !ok {
			t.Errorf("missing description for %q", key)
		}
	}

	for key, desc := range result {
		if desc == "" {
			t.Errorf("empty description for %q", key)
		}
	}
}

func TestGetContextTypeDescriptionsEmptyService(t *testing.T) {
	service := NewService()
	result := service.GetContextTypeDescriptions()
	if len(result) != 0 {
		t.Errorf("expected empty map, got %d entries", len(result))
	}
}
