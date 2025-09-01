package orgdatacore

import (
	"reflect"
	"sort"
	"testing"
)

// TestGetTeamByName tests team lookup by name
func TestGetTeamByName(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name         string
		teamName     string
		expectFound  bool
		expectedName string
	}{
		{
			name:         "existing team",
			teamName:     "test-team",
			expectFound:  true,
			expectedName: "test-team",
		},
		{
			name:         "another existing team",
			teamName:     "platform-team",
			expectFound:  true,
			expectedName: "platform-team",
		},
		{
			name:        "nonexistent team",
			teamName:    "nonexistent-team",
			expectFound: false,
		},
		{
			name:        "empty team name",
			teamName:    "",
			expectFound: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetTeamByName(tt.teamName)

			if tt.expectFound {
				if result == nil {
					t.Errorf("GetTeamByName(%q) returned nil, expected team", tt.teamName)
				} else if result.Name != tt.expectedName {
					t.Errorf("GetTeamByName(%q) returned team with name %q, expected %q", tt.teamName, result.Name, tt.expectedName)
				}
			} else {
				if result != nil {
					t.Errorf("GetTeamByName(%q) returned %+v, expected nil", tt.teamName, result)
				}
			}
		})
	}
}

// TestGetTeamsForUID tests team membership lookup by UID
func TestGetTeamsForUID(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		uid      string
		expected []string
	}{
		{
			name:     "jsmith teams",
			uid:      "jsmith",
			expected: []string{"test-team"},
		},
		{
			name:     "bwilson teams",
			uid:      "bwilson",
			expected: []string{"platform-team"},
		},
		{
			name:     "nonexistent user",
			uid:      "nonexistent",
			expected: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetTeamsForUID(tt.uid)

			// Sort both slices to ensure consistent comparison
			sort.Strings(result)
			sort.Strings(tt.expected)

			// Handle nil vs empty slice comparison
			if len(result) == 0 && len(tt.expected) == 0 {
				// Both are empty - this is fine
			} else if !reflect.DeepEqual(result, tt.expected) {
				t.Errorf("GetTeamsForUID(%q) = %v, expected %v", tt.uid, result, tt.expected)
			}
		})
	}
}

// TestGetTeamsForSlackID tests team membership lookup by Slack ID
func TestGetTeamsForSlackID(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		slackID  string
		expected []string
	}{
		{
			name:     "jsmith slack teams",
			slackID:  "U12345678",
			expected: []string{"test-team"},
		},
		{
			name:     "bwilson slack teams",
			slackID:  "U98765432",
			expected: []string{"platform-team"},
		},
		{
			name:     "nonexistent slack user",
			slackID:  "U99999999",
			expected: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetTeamsForSlackID(tt.slackID)

			sort.Strings(result)
			sort.Strings(tt.expected)

			if !reflect.DeepEqual(result, tt.expected) {
				t.Errorf("GetTeamsForSlackID(%q) = %v, expected %v", tt.slackID, result, tt.expected)
			}
		})
	}
}

// TestGetTeamMembers tests team member retrieval
func TestGetTeamMembers(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name         string
		teamName     string
		expectedUIDs []string
	}{
		{
			name:         "test-team members",
			teamName:     "test-team",
			expectedUIDs: []string{"jsmith", "adoe"},
		},
		{
			name:         "platform-team members",
			teamName:     "platform-team",
			expectedUIDs: []string{"bwilson"},
		},
		{
			name:         "nonexistent team",
			teamName:     "nonexistent-team",
			expectedUIDs: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetTeamMembers(tt.teamName)

			// Extract UIDs from result
			var resultUIDs []string
			for _, emp := range result {
				resultUIDs = append(resultUIDs, emp.UID)
			}

			sort.Strings(resultUIDs)
			sort.Strings(tt.expectedUIDs)

			// Handle nil vs empty slice comparison
			if len(resultUIDs) == 0 && len(tt.expectedUIDs) == 0 {
				// Both are empty - this is fine
			} else if !reflect.DeepEqual(resultUIDs, tt.expectedUIDs) {
				t.Errorf("GetTeamMembers(%q) UIDs = %v, expected %v", tt.teamName, resultUIDs, tt.expectedUIDs)
			}

			// Verify that returned employees have all fields populated
			for _, emp := range result {
				if emp.UID == "" || emp.FullName == "" || emp.Email == "" {
					t.Errorf("GetTeamMembers(%q) returned incomplete employee data: %+v", tt.teamName, emp)
				}
			}
		})
	}
}

// TestIsEmployeeInTeam tests team membership checks
func TestIsEmployeeInTeam(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		uid      string
		teamName string
		expected bool
	}{
		{
			name:     "jsmith in test-team",
			uid:      "jsmith",
			teamName: "test-team",
			expected: true,
		},
		{
			name:     "bwilson in platform-team",
			uid:      "bwilson",
			teamName: "platform-team",
			expected: true,
		},
		{
			name:     "jsmith not in platform-team",
			uid:      "jsmith",
			teamName: "platform-team",
			expected: false,
		},
		{
			name:     "nonexistent user",
			uid:      "nonexistent",
			teamName: "test-team",
			expected: false,
		},
		{
			name:     "user in nonexistent team",
			uid:      "jsmith",
			teamName: "nonexistent-team",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.IsEmployeeInTeam(tt.uid, tt.teamName)
			if result != tt.expected {
				t.Errorf("IsEmployeeInTeam(%q, %q) = %v, expected %v", tt.uid, tt.teamName, result, tt.expected)
			}
		})
	}
}

// TestIsSlackUserInTeam tests Slack user team membership checks
func TestIsSlackUserInTeam(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		slackID  string
		teamName string
		expected bool
	}{
		{
			name:     "jsmith slack in test-team",
			slackID:  "U12345678",
			teamName: "test-team",
			expected: true,
		},
		{
			name:     "bwilson slack in platform-team",
			slackID:  "U98765432",
			teamName: "platform-team",
			expected: true,
		},
		{
			name:     "jsmith slack not in platform-team",
			slackID:  "U12345678",
			teamName: "platform-team",
			expected: false,
		},
		{
			name:     "nonexistent slack user",
			slackID:  "U99999999",
			teamName: "test-team",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.IsSlackUserInTeam(tt.slackID, tt.teamName)
			if result != tt.expected {
				t.Errorf("IsSlackUserInTeam(%q, %q) = %v, expected %v", tt.slackID, tt.teamName, result, tt.expected)
			}
		})
	}
}

// TestTeamMembershipConsistency tests consistency between different team queries
func TestTeamMembershipConsistency(t *testing.T) {
	service := setupTestService(t)

	// Get team members
	members := service.GetTeamMembers("test-team")

	// Each member should show up in GetTeamsForUID
	for _, member := range members {
		teams := service.GetTeamsForUID(member.UID)
		found := false
		for _, team := range teams {
			if team == "test-team" {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("Employee %s is member of test-team but GetTeamsForUID doesn't show it", member.UID)
		}

		// IsEmployeeInTeam should also return true
		if !service.IsEmployeeInTeam(member.UID, "test-team") {
			t.Errorf("Employee %s is member of test-team but IsEmployeeInTeam returns false", member.UID)
		}
	}
}
