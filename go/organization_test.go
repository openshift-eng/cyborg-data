package orgdatacore

import (
	"testing"
)

// TestGetOrgByName tests organization lookup by name
func TestGetOrgByName(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name         string
		orgName      string
		expectFound  bool
		expectedName string
	}{
		{
			name:         "existing org",
			orgName:      "test-org",
			expectFound:  true,
			expectedName: "test-org",
		},
		{
			name:         "another existing org",
			orgName:      "platform-org",
			expectFound:  true,
			expectedName: "platform-org",
		},
		{
			name:        "nonexistent org",
			orgName:     "nonexistent-org",
			expectFound: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetOrgByName(tt.orgName)

			if tt.expectFound {
				if result == nil {
					t.Errorf("GetOrgByName(%q) returned nil, expected org", tt.orgName)
				} else if result.Name != tt.expectedName {
					t.Errorf("GetOrgByName(%q) returned org with name %q, expected %q", tt.orgName, result.Name, tt.expectedName)
				}
			} else {
				if result != nil {
					t.Errorf("GetOrgByName(%q) returned %+v, expected nil", tt.orgName, result)
				}
			}
		})
	}
}

// TestIsEmployeeInOrg tests organization membership checks
func TestIsEmployeeInOrg(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		uid      string
		orgName  string
		expected bool
	}{
		{
			name:     "jsmith in test-org (direct)",
			uid:      "jsmith",
			orgName:  "test-org",
			expected: true,
		},
		{
			name:     "bwilson in platform-org",
			uid:      "bwilson",
			orgName:  "platform-org",
			expected: true,
		},
		{
			name:     "bwilson in test-org (via team inheritance)",
			uid:      "bwilson",
			orgName:  "test-org",
			expected: true, // platform-team is in test-org via ancestry
		},
		{
			name:     "jsmith not in platform-org",
			uid:      "jsmith",
			orgName:  "platform-org",
			expected: false,
		},
		{
			name:     "nonexistent user",
			uid:      "nonexistent",
			orgName:  "test-org",
			expected: false,
		},
		{
			name:     "user in nonexistent org",
			uid:      "jsmith",
			orgName:  "nonexistent-org",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.IsEmployeeInOrg(tt.uid, tt.orgName)
			if result != tt.expected {
				t.Errorf("IsEmployeeInOrg(%q, %q) = %v, expected %v", tt.uid, tt.orgName, result, tt.expected)
			}
		})
	}
}

// TestIsSlackUserInOrg tests Slack user organization membership checks
func TestIsSlackUserInOrg(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		slackID  string
		orgName  string
		expected bool
	}{
		{
			name:     "jsmith slack in test-org",
			slackID:  "U12345678",
			orgName:  "test-org",
			expected: true,
		},
		{
			name:     "bwilson slack in platform-org",
			slackID:  "U98765432",
			orgName:  "platform-org",
			expected: true,
		},
		{
			name:     "bwilson slack in test-org (via team)",
			slackID:  "U98765432",
			orgName:  "test-org",
			expected: true,
		},
		{
			name:     "nonexistent slack user",
			slackID:  "U99999999",
			orgName:  "test-org",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.IsSlackUserInOrg(tt.slackID, tt.orgName)
			if result != tt.expected {
				t.Errorf("IsSlackUserInOrg(%q, %q) = %v, expected %v", tt.slackID, tt.orgName, result, tt.expected)
			}
		})
	}
}

// TestGetUserOrganizations tests complete organizational hierarchy retrieval
func TestGetUserOrganizations(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		slackID  string
		contains []OrgInfo // Check that result contains at least these items
	}{
		{
			name:    "jsmith organizations",
			slackID: "U12345678",
			contains: []OrgInfo{
				{Name: "test-team", Type: "Team"},
				{Name: "test-org", Type: "Organization"},
			},
		},
		{
			name:    "bwilson organizations",
			slackID: "U98765432",
			contains: []OrgInfo{
				{Name: "platform-team", Type: "Team"},
				{Name: "platform-org", Type: "Organization"},
				{Name: "test-org", Type: "Organization"},
				{Name: "engineering", Type: "Pillar"},
				{Name: "backend-teams", Type: "Team Group"},
			},
		},
		{
			name:     "nonexistent slack user",
			slackID:  "U99999999",
			contains: []OrgInfo{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetUserOrganizations(tt.slackID)

			// Check that all expected items are present
			for _, expected := range tt.contains {
				found := false
				for _, actual := range result {
					if actual.Name == expected.Name && actual.Type == expected.Type {
						found = true
						break
					}
				}
				if !found {
					t.Errorf("GetUserOrganizations(%q) missing expected item: %+v", tt.slackID, expected)
					t.Errorf("Actual results: %+v", result)
				}
			}

			// Check that no duplicates exist
			seen := make(map[string]bool)
			for _, org := range result {
				key := org.Name + ":" + org.Type
				if seen[key] {
					t.Errorf("GetUserOrganizations(%q) returned duplicate: %+v", tt.slackID, org)
				}
				seen[key] = true
			}
		})
	}
}

// TestOrganizationalHierarchy tests the team-to-org inheritance
func TestOrganizationalHierarchy(t *testing.T) {
	service := setupTestService(t)

	// bwilson is in platform-team, which belongs to both platform-org and test-org
	// So bwilson should be in both organizations

	if !service.IsEmployeeInOrg("bwilson", "platform-org") {
		t.Error("bwilson should be in platform-org directly")
	}

	if !service.IsEmployeeInOrg("bwilson", "test-org") {
		t.Error("bwilson should be in test-org via team hierarchy")
	}

	// jsmith should only be in test-org, not platform-org
	if !service.IsEmployeeInOrg("jsmith", "test-org") {
		t.Error("jsmith should be in test-org")
	}

	if service.IsEmployeeInOrg("jsmith", "platform-org") {
		t.Error("jsmith should NOT be in platform-org")
	}
}

// TestOrgInfoTypes tests that correct OrgInfo types are returned
func TestOrgInfoTypes(t *testing.T) {
	service := setupTestService(t)

	orgs := service.GetUserOrganizations("U98765432") // bwilson

	typeMap := make(map[string]string)
	for _, org := range orgs {
		typeMap[org.Name] = org.Type
	}

	expectedTypes := map[string]string{
		"platform-team": "Team",
		"platform-org":  "Organization",
		"test-org":      "Organization",
		"engineering":   "Pillar",
		"backend-teams": "Team Group",
	}

	for name, expectedType := range expectedTypes {
		if actualType, exists := typeMap[name]; exists {
			if actualType != expectedType {
				t.Errorf("Expected %s to have type %s, got %s", name, expectedType, actualType)
			}
		} else {
			t.Errorf("Expected to find %s in user organizations", name)
		}
	}
}
