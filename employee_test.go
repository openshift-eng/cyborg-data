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
				UID:        "jsmith",
				FullName:   "John Smith",
				Email:      "jsmith@example.com",
				JobTitle:   "Software Engineer",
				SlackUID:   "U12345678",
				GitHubID:   "jsmith-dev",
				ManagerUID: "adoe",
			},
		},
		{
			name: "existing employee adoe",
			uid:  "adoe",
			expected: &Employee{
				UID:             "adoe",
				FullName:        "Alice Doe",
				Email:           "adoe@example.com",
				JobTitle:        "Team Lead",
				SlackUID:        "U87654321",
				GitHubID:        "alice-codes",
				IsPeopleManager: true,
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
				UID:        "jsmith",
				FullName:   "John Smith",
				Email:      "jsmith@example.com",
				JobTitle:   "Software Engineer",
				SlackUID:   "U12345678",
				GitHubID:   "jsmith-dev",
				ManagerUID: "adoe",
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
				GitHubID: "bobw",
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
			githubID: "jsmith-dev",
			expected: &Employee{
				UID:        "jsmith",
				FullName:   "John Smith",
				Email:      "jsmith@example.com",
				JobTitle:   "Software Engineer",
				SlackUID:   "U12345678",
				GitHubID:   "jsmith-dev",
				ManagerUID: "adoe",
			},
		},
		{
			name:     "existing github ID for bwilson",
			githubID: "bobw",
			expected: &Employee{
				UID:      "bwilson",
				FullName: "Bob Wilson",
				Email:    "bwilson@example.com",
				JobTitle: "Senior Engineer",
				SlackUID: "U98765432",
				GitHubID: "bobw",
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
	if emp.GitHubID != "jsmith-dev" {
		t.Errorf("Expected GitHubID 'jsmith-dev', got '%s'", emp.GitHubID)
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
		{"jsmith", "jsmith-dev"},
		{"adoe", "alice-codes"},
		{"bwilson", "bobw"},
	}

	for _, tt := range tests {
		t.Run(tt.uid, func(t *testing.T) {
			// Test UID -> Employee -> SlackID
			emp := service.GetEmployeeByUID(tt.uid)
			if emp == nil {
				t.Fatalf("Employee %s not found", tt.uid)
			}
			if emp.GitHubID != tt.githubID {
				t.Errorf("Expected GitHubID %s, got %s", tt.githubID, emp.GitHubID)
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

// TestNewEmployeeFields tests the new employee fields added in refactoring
func TestNewEmployeeFields(t *testing.T) {
	service := NewService()
	service.data = &Data{
		Lookups: Lookups{
			Employees: map[string]Employee{
				"testuser": {
					UID:             "testuser",
					FullName:        "Test User",
					Email:           "test@example.com",
					JobTitle:        "Engineer",
					SlackUID:        "U123",
					GitHubID:        "testgithub",
					RhatGeo:         "NA",
					CostCenter:      12345,
					ManagerUID:      "manager1",
					IsPeopleManager: false,
				},
			},
		},
	}

	emp := service.GetEmployeeByUID("testuser")
	if emp == nil {
		t.Fatal("expected employee, got nil")
	}

	if emp.GitHubID != "testgithub" {
		t.Errorf("expected GitHubID 'testgithub', got '%s'", emp.GitHubID)
	}
	if emp.RhatGeo != "NA" {
		t.Errorf("expected RhatGeo 'NA', got '%s'", emp.RhatGeo)
	}
	if emp.CostCenter != 12345 {
		t.Errorf("expected CostCenter 12345, got %d", emp.CostCenter)
	}
	if emp.ManagerUID != "manager1" {
		t.Errorf("expected ManagerUID 'manager1', got '%s'", emp.ManagerUID)
	}
	if emp.IsPeopleManager != false {
		t.Errorf("expected IsPeopleManager false, got %v", emp.IsPeopleManager)
	}
}

// TestGetManagerForEmployee tests manager lookup functionality
func TestGetManagerForEmployee(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name            string
		uid             string
		expectedManager *Employee
	}{
		{
			name: "employee with manager",
			uid:  "jsmith",
			expectedManager: &Employee{
				UID:             "adoe",
				FullName:        "Alice Doe",
				Email:           "adoe@example.com",
				JobTitle:        "Team Lead",
				SlackUID:        "U87654321",
				GitHubID:        "alice-codes",
				IsPeopleManager: true,
			},
		},
		{
			name:            "employee without manager",
			uid:             "bwilson",
			expectedManager: nil,
		},
		{
			name:            "people manager (adoe has no manager)",
			uid:             "adoe",
			expectedManager: nil,
		},
		{
			name:            "nonexistent employee",
			uid:             "nonexistent",
			expectedManager: nil,
		},
		{
			name:            "empty UID",
			uid:             "",
			expectedManager: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.GetManagerForEmployee(tt.uid)
			if !reflect.DeepEqual(result, tt.expectedManager) {
				t.Errorf("GetManagerForEmployee(%q) = %+v, expected %+v", tt.uid, result, tt.expectedManager)
			}
		})
	}
}
