package orgdatacore

import (
	"slices"
	"testing"
)

func TestAllEmployeeUIDs(t *testing.T) {
	service := setupTestService(t)

	// Collect all UIDs from iterator
	var uids []string
	for uid := range service.AllEmployeeUIDs() {
		uids = append(uids, uid)
	}

	// Should have 3 employees in test data
	if len(uids) != 3 {
		t.Errorf("Expected 3 employee UIDs, got %d", len(uids))
	}

	// Check that expected UIDs are present
	expectedUIDs := []string{"jsmith", "adoe", "bwilson"}
	for _, expected := range expectedUIDs {
		if !slices.Contains(uids, expected) {
			t.Errorf("Expected UID %q not found in iterator results", expected)
		}
	}
}

func TestAllEmployeeUIDs_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllEmployeeUIDs() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 UIDs from empty service, got %d", count)
	}
}

func TestAllEmployees(t *testing.T) {
	service := setupTestService(t)

	// Collect all employees from iterator
	var employees []*Employee
	for emp := range service.AllEmployees() {
		employees = append(employees, emp)
	}

	// Should have 3 employees in test data
	if len(employees) != 3 {
		t.Errorf("Expected 3 employees, got %d", len(employees))
	}

	// Check that employees have valid data
	for _, emp := range employees {
		if emp.UID == "" {
			t.Error("Employee has empty UID")
		}
		if emp.FullName == "" {
			t.Error("Employee has empty FullName")
		}
	}
}

func TestAllEmployees_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllEmployees() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 employees from empty service, got %d", count)
	}
}

func TestAllTeamNames(t *testing.T) {
	service := setupTestService(t)

	var names []string
	for name := range service.AllTeamNames() {
		names = append(names, name)
	}

	// Should have teams in test data
	if len(names) == 0 {
		t.Error("Expected at least one team name")
	}

	// Check expected teams are present
	if !slices.Contains(names, "test-team") {
		t.Error("Expected 'test-team' in team names")
	}
}

func TestAllTeamNames_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllTeamNames() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 team names from empty service, got %d", count)
	}
}

func TestAllTeams(t *testing.T) {
	service := setupTestService(t)

	var teams []*Team
	teamNames := make(map[string]bool)
	for name, team := range service.AllTeams() {
		teams = append(teams, team)
		teamNames[name] = true
	}

	// Should have teams in test data
	if len(teams) == 0 {
		t.Error("Expected at least one team")
	}

	// Check that key matches team name
	for name, team := range service.AllTeams() {
		if team.Name != name {
			t.Errorf("Key %q doesn't match team name %q", name, team.Name)
		}
	}
}

func TestAllTeams_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllTeams() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 teams from empty service, got %d", count)
	}
}

func TestAllOrgNames(t *testing.T) {
	service := setupTestService(t)

	var names []string
	for name := range service.AllOrgNames() {
		names = append(names, name)
	}

	// Should have orgs in test data
	if len(names) == 0 {
		t.Error("Expected at least one org name")
	}

	// Check expected orgs are present
	if !slices.Contains(names, "test-org") {
		t.Error("Expected 'test-org' in org names")
	}
}

func TestAllOrgNames_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllOrgNames() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 org names from empty service, got %d", count)
	}
}

func TestAllOrgs(t *testing.T) {
	service := setupTestService(t)

	count := 0
	for name, org := range service.AllOrgs() {
		count++
		if org.Name != name {
			t.Errorf("Key %q doesn't match org name %q", name, org.Name)
		}
	}

	// Should have orgs in test data
	if count == 0 {
		t.Error("Expected at least one org")
	}
}

func TestAllOrgs_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllOrgs() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 orgs from empty service, got %d", count)
	}
}

func TestAllPillarNames(t *testing.T) {
	service := setupTestService(t)

	var names []string
	for name := range service.AllPillarNames() {
		names = append(names, name)
	}

	// May or may not have pillars in test data
	// Just verify it doesn't panic
	_ = names
}

func TestAllPillarNames_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllPillarNames() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 pillar names from empty service, got %d", count)
	}
}

func TestAllPillars(t *testing.T) {
	service := setupTestService(t)

	for name, pillar := range service.AllPillars() {
		if pillar.Name != name {
			t.Errorf("Key %q doesn't match pillar name %q", name, pillar.Name)
		}
	}
}

func TestAllPillars_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllPillars() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 pillars from empty service, got %d", count)
	}
}

func TestAllTeamGroupNames(t *testing.T) {
	service := setupTestService(t)

	var names []string
	for name := range service.AllTeamGroupNames() {
		names = append(names, name)
	}

	// May or may not have team groups in test data
	// Just verify it doesn't panic
	_ = names
}

func TestAllTeamGroupNames_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllTeamGroupNames() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 team group names from empty service, got %d", count)
	}
}

func TestAllTeamGroups(t *testing.T) {
	service := setupTestService(t)

	for name, teamGroup := range service.AllTeamGroups() {
		if teamGroup.Name != name {
			t.Errorf("Key %q doesn't match team group name %q", name, teamGroup.Name)
		}
	}
}

func TestAllTeamGroups_EmptyService(t *testing.T) {
	service := NewService()

	count := 0
	for range service.AllTeamGroups() {
		count++
	}

	if count != 0 {
		t.Errorf("Expected 0 team groups from empty service, got %d", count)
	}
}

func TestIterator_EarlyBreak(t *testing.T) {
	service := setupTestService(t)

	// Test that early break works correctly
	count := 0
	for range service.AllEmployeeUIDs() {
		count++
		if count >= 1 {
			break
		}
	}

	if count != 1 {
		t.Errorf("Expected to break after 1 iteration, got %d", count)
	}
}

func TestIterator_MultipleIterations(t *testing.T) {
	service := setupTestService(t)

	// First iteration
	count1 := 0
	for range service.AllEmployeeUIDs() {
		count1++
	}

	// Second iteration should return same results
	count2 := 0
	for range service.AllEmployeeUIDs() {
		count2++
	}

	if count1 != count2 {
		t.Errorf("Multiple iterations returned different counts: %d vs %d", count1, count2)
	}
}
