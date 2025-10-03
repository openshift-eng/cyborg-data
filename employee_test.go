package orgdatacore

import (
	"reflect"
	"testing"
)

// TestGetEmployeeByUID tests employee lookup by UID
func TestGetEmployeeByUID(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		uid      string
		expected *Employee
	}{
		{
			name: "existing employee jsmith",
			uid:  "jsmith",
			expected: &Employee{
				UID:      "jsmith",
				FullName: "John Smith",
				Email:    "jsmith@example.com",
				JobTitle: "Software Engineer",
				SlackUID: "U12345678",
				GithubID: "jsmith",
			},
		},
		{
			name: "existing employee adoe",
			uid:  "adoe",
			expected: &Employee{
				UID:      "adoe",
				FullName: "Alice Doe",
				Email:    "adoe@example.com",
				JobTitle: "Team Lead",
				SlackUID: "U87654321",
				GithubID: "adeer",
			},
		},
		{
			name:     "nonexistent employee",
			uid:      "nonexistent",
			expected: nil,
		},
		{
			name:     "empty UID",
			uid:      "",
			expected: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetEmployeeByUID(tt.uid)
			if !reflect.DeepEqual(result, tt.expected) {
				t.Errorf("GetEmployeeByUID(%q) = %+v, expected %+v", tt.uid, result, tt.expected)
			}
		})
	}
}

// TestGetEmployeeBySlackID tests employee lookup by Slack ID
func TestGetEmployeeBySlackID(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		slackID  string
		expected *Employee
	}{
		{
			name:    "existing slack ID for jsmith",
			slackID: "U12345678",
			expected: &Employee{
				UID:      "jsmith",
				FullName: "John Smith",
				Email:    "jsmith@example.com",
				JobTitle: "Software Engineer",
				SlackUID: "U12345678",
				GithubID: "jsmith",
			},
		},
		{
			name:    "existing slack ID for bwilson",
			slackID: "U98765432",
			expected: &Employee{
				UID:      "bwilson",
				FullName: "Bob Wilson",
				Email:    "bwilson@example.com",
				JobTitle: "Senior Engineer",
				SlackUID: "U98765432",
				GithubID: "l33tCoder1",
			},
		},
		{
			name:     "nonexistent slack ID",
			slackID:  "U99999999",
			expected: nil,
		},
		{
			name:     "empty slack ID",
			slackID:  "",
			expected: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetEmployeeBySlackID(tt.slackID)
			if !reflect.DeepEqual(result, tt.expected) {
				t.Errorf("GetEmployeeBySlackID(%q) = %+v, expected %+v", tt.slackID, result, tt.expected)
			}
		})
	}
}

// TestGetEmployeeByGitHubID tests employee lookup by Slack ID
func TestGetEmployeeByGitHubID(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name     string
		githubID string
		expected *Employee
	}{
		{
			name:     "existing github ID for jsmith",
			githubID: "jsmith",
			expected: &Employee{
				UID:      "jsmith",
				FullName: "John Smith",
				Email:    "jsmith@example.com",
				JobTitle: "Software Engineer",
				SlackUID: "U12345678",
				GithubID: "jsmith",
			},
		},
		{
			name:     "existing github ID for bwilson",
			githubID: "l33tCoder1",
			expected: &Employee{
				UID:      "bwilson",
				FullName: "Bob Wilson",
				Email:    "bwilson@example.com",
				JobTitle: "Senior Engineer",
				SlackUID: "U98765432",
				GithubID: "l33tCoder1",
			},
		},
		{
			name:     "nonexistent github ID",
			githubID: "hackerx",
			expected: nil,
		},
		{
			name:     "empty github ID",
			githubID: "",
			expected: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetEmployeeByGitHubID(tt.githubID)
			if !reflect.DeepEqual(result, tt.expected) {
				t.Errorf("GetEmployeeByGitHubID(%q) = %+v, expected %+v", tt.githubID, result, tt.expected)
			}
		})
	}
}

// TestEmployeeFields tests that all employee fields are properly loaded
func TestEmployeeFields(t *testing.T) {
	service := setupTestService(t)

	emp := service.GetEmployeeByUID("jsmith")
	if emp == nil {
		t.Fatal("Expected to find employee jsmith")
	}

	// Test all fields are populated
	if emp.UID != "jsmith" {
		t.Errorf("Expected UID 'jsmith', got '%s'", emp.UID)
	}
	if emp.FullName != "John Smith" {
		t.Errorf("Expected FullName 'John Smith', got '%s'", emp.FullName)
	}
	if emp.Email != "jsmith@example.com" {
		t.Errorf("Expected Email 'jsmith@example.com', got '%s'", emp.Email)
	}
	if emp.JobTitle != "Software Engineer" {
		t.Errorf("Expected JobTitle 'Software Engineer', got '%s'", emp.JobTitle)
	}
	if emp.SlackUID != "U12345678" {
		t.Errorf("Expected SlackUID 'U12345678', got '%s'", emp.SlackUID)
	}
	if emp.GithubID != "jsmith" {
		t.Errorf("Expected GitHubID 'jsmith', got '%s'", emp.GithubID)
	}
}

// TestSlackIDMapping tests the bidirectional Slack ID mapping
func TestSlackIDMapping(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		uid     string
		slackID string
	}{
		{"jsmith", "U12345678"},
		{"adoe", "U87654321"},
		{"bwilson", "U98765432"},
	}

	for _, tt := range tests {
		t.Run(tt.uid, func(t *testing.T) {
			// Test UID -> Employee -> SlackID
			emp := service.GetEmployeeByUID(tt.uid)
			if emp == nil {
				t.Fatalf("Employee %s not found", tt.uid)
			}
			if emp.SlackUID != tt.slackID {
				t.Errorf("Expected SlackUID %s, got %s", tt.slackID, emp.SlackUID)
			}

			// Test SlackID -> Employee -> UID
			empBySlack := service.GetEmployeeBySlackID(tt.slackID)
			if empBySlack == nil {
				t.Fatalf("Employee with slack ID %s not found", tt.slackID)
			}
			if empBySlack.UID != tt.uid {
				t.Errorf("Expected UID %s, got %s", tt.uid, empBySlack.UID)
			}

			// Ensure they're the same employee
			if !reflect.DeepEqual(emp, empBySlack) {
				t.Error("Employee lookup by UID and SlackID should return same result")
			}
		})
	}
}

// TestGitHubIDMapping tests the bidirectional Slack ID mapping
func TestGitHubIDMapping(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		uid      string
		githubID string
	}{
		{"jsmith", "jsmith"},
		{"adoe", "adeer"},
		{"bwilson", "l33tCoder1"},
	}

	for _, tt := range tests {
		t.Run(tt.uid, func(t *testing.T) {
			// Test UID -> Employee -> SlackID
			emp := service.GetEmployeeByUID(tt.uid)
			if emp == nil {
				t.Fatalf("Employee %s not found", tt.uid)
			}
			if emp.GithubID != tt.githubID {
				t.Errorf("Expected SlackUID %s, got %s", tt.githubID, emp.GithubID)
			}

			// Test GitHubId -> Employee -> UID
			empByGitHub := service.GetEmployeeByGitHubID(tt.githubID)
			if empByGitHub == nil {
				t.Fatalf("Employee with github ID %s not found", tt.githubID)
			}
			if empByGitHub.UID != tt.uid {
				t.Errorf("Expected UID %s, got %s", tt.uid, empByGitHub.UID)
			}

			// Ensure they're the same employee
			if !reflect.DeepEqual(emp, empByGitHub) {
				t.Error("Employee lookup by UID and GitHubID should return same result")
			}
		})
	}
}
