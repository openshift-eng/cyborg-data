package orgdatacore

import (
	"context"
	"io"
	"path/filepath"
	"testing"
	"time"
)

// TestServiceWithNoData tests service behavior before data is loaded
func TestServiceWithNoData(t *testing.T) {
	service := NewService()

	// All queries should return empty/nil results
	if emp := service.GetEmployeeByUID("test"); emp != nil {
		t.Error("GetEmployeeByUID should return nil with no data loaded")
	}

	if emp := service.GetEmployeeBySlackID("U123"); emp != nil {
		t.Error("GetEmployeeBySlackID should return nil with no data loaded")
	}

	if team := service.GetTeamByName("test"); team != nil {
		t.Error("GetTeamByName should return nil with no data loaded")
	}

	if org := service.GetOrgByName("test"); org != nil {
		t.Error("GetOrgByName should return nil with no data loaded")
	}

	if teams := service.GetTeamsForUID("test"); len(teams) != 0 {
		t.Error("GetTeamsForUID should return empty slice with no data loaded")
	}

	if members := service.GetTeamMembers("test"); len(members) != 0 {
		t.Error("GetTeamMembers should return empty slice with no data loaded")
	}

	if result := service.IsEmployeeInTeam("test", "test"); result {
		t.Error("IsEmployeeInTeam should return false with no data loaded")
	}

	if result := service.IsEmployeeInOrg("test", "test"); result {
		t.Error("IsEmployeeInOrg should return false with no data loaded")
	}

	if orgs := service.GetUserOrganizations("U123"); len(orgs) != 0 {
		t.Error("GetUserOrganizations should return empty slice with no data loaded")
	}
}

// TestServiceErrorHandling tests various error conditions
func TestServiceErrorHandling(t *testing.T) {
	service := setupTestService(t)

	tests := []struct {
		name string
		test func(t *testing.T)
	}{
		{
			name: "nil and empty string handling",
			test: func(t *testing.T) {
				// Empty string parameters
				if emp := service.GetEmployeeByUID(""); emp != nil {
					t.Error("GetEmployeeByUID with empty string should return nil")
				}

				if emp := service.GetEmployeeBySlackID(""); emp != nil {
					t.Error("GetEmployeeBySlackID with empty string should return nil")
				}

				if team := service.GetTeamByName(""); team != nil {
					t.Error("GetTeamByName with empty string should return nil")
				}

				if org := service.GetOrgByName(""); org != nil {
					t.Error("GetOrgByName with empty string should return nil")
				}
			},
		},
		{
			name: "nonexistent data handling",
			test: func(t *testing.T) {
				// All these should return safe defaults, not crash
				teams := service.GetTeamsForUID("nonexistent")
				if len(teams) != 0 {
					t.Error("GetTeamsForUID for nonexistent user should return empty result")
				}

				members := service.GetTeamMembers("nonexistent-team")
				if len(members) != 0 {
					t.Error("GetTeamMembers for nonexistent team should return empty result")
				}

				orgs := service.GetUserOrganizations("U99999999")
				if len(orgs) != 0 {
					t.Error("GetUserOrganizations for nonexistent user should return empty result")
				}
			},
		},
		{
			name: "special characters in IDs",
			test: func(t *testing.T) {
				// These should not cause panics
				service.GetEmployeeByUID("user@domain.com")
				service.GetTeamByName("team-with-dashes_and_underscores")
				service.GetOrgByName("org.with.dots")
				service.IsEmployeeInTeam("user-123", "team_456")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, tt.test)
	}
}

// TestConcurrentAccess tests thread safety of the service
func TestConcurrentAccess(t *testing.T) {
	service := setupTestService(t)

	// Test concurrent reads
	done := make(chan bool, 10)

	for i := 0; i < 10; i++ {
		go func(id int) {
			defer func() { done <- true }()

			// Perform various read operations
			service.GetEmployeeByUID("jsmith")
			service.GetTeamByName("test-team")
			service.IsEmployeeInTeam("jsmith", "test-team")
			service.GetVersion()
			service.GetUserOrganizations("U12345678")
		}(i)
	}

	// Wait for all goroutines to complete
	for i := 0; i < 10; i++ {
		select {
		case <-done:
			// OK
		case <-time.After(5 * time.Second):
			t.Fatal("Timeout waiting for concurrent operations")
		}
	}
}

// TestConcurrentReadWrite tests concurrent read/write safety
func TestConcurrentReadWrite(t *testing.T) {
	service := NewService()

	// Load initial data
	testDataPath := filepath.Join("testdata", "test_org_data.json")
	fileSource := NewFileDataSource(testDataPath)
	if err := service.LoadFromDataSource(context.Background(), fileSource); err != nil {
		t.Fatalf("Failed to load initial data: %v", err)
	}

	done := make(chan bool, 11)

	// Start 10 concurrent readers
	for i := 0; i < 10; i++ {
		go func() {
			defer func() { done <- true }()

			for j := 0; j < 100; j++ {
				service.GetEmployeeByUID("jsmith")
				service.GetTeamMembers("test-team")
				time.Sleep(1 * time.Millisecond) // Small delay
			}
		}()
	}

	// Start 1 writer that reloads data
	go func() {
		defer func() { done <- true }()

		for j := 0; j < 5; j++ {
			time.Sleep(50 * time.Millisecond)
			service.LoadFromDataSource(context.Background(), fileSource)
		}
	}()

	// Wait for all operations to complete
	for i := 0; i < 11; i++ {
		select {
		case <-done:
			// OK
		case <-time.After(10 * time.Second):
			t.Fatal("Timeout waiting for concurrent read/write operations")
		}
	}
}

// TestReloadData tests that data can be reloaded
func TestReloadData(t *testing.T) {
	service := NewService()

	// Initial state - no data
	version1 := service.GetVersion()
	if version1.EmployeeCount != 0 {
		t.Error("Initial employee count should be 0")
	}

	// Load data for the first time
	testDataPath := filepath.Join("testdata", "test_org_data.json")
	fileSource := NewFileDataSource(testDataPath)
	err := service.LoadFromDataSource(context.Background(), fileSource)
	if err != nil {
		t.Fatalf("Failed to load data: %v", err)
	}

	version2 := service.GetVersion()
	if version2.EmployeeCount != 3 {
		t.Errorf("Expected 3 employees after loading, got %d", version2.EmployeeCount)
	}

	// Ensure time changed
	if !version2.LoadTime.After(version1.LoadTime) {
		t.Error("LoadTime should be updated after loading data")
	}

	// Reload the same data
	time.Sleep(1 * time.Millisecond) // Ensure time difference
	err = service.LoadFromDataSource(context.Background(), fileSource)
	if err != nil {
		t.Fatalf("Failed to reload data: %v", err)
	}

	version3 := service.GetVersion()
	if version3.EmployeeCount != 3 {
		t.Errorf("Expected 3 employees after reloading, got %d", version3.EmployeeCount)
	}

	// Time should be updated
	if !version3.LoadTime.After(version2.LoadTime) {
		t.Error("LoadTime should be updated after reloading data")
	}

	// Data should still be accessible
	emp := service.GetEmployeeByUID("jsmith")
	if emp == nil {
		t.Error("Employee should still be accessible after reload")
	}
}

// TestInvalidJSONHandling tests handling of invalid JSON data
func TestInvalidJSONHandling(t *testing.T) {
	service := NewService()

	// Create a fake data source that returns invalid JSON
	invalidSource := &testDataSource{
		data: `{"invalid": json}`,
		err:  nil,
	}

	err := service.LoadFromDataSource(context.Background(), invalidSource)
	if err == nil {
		t.Error("Expected error when loading invalid JSON")
	}

	// Service should still be usable (no data loaded)
	if emp := service.GetEmployeeByUID("test"); emp != nil {
		t.Error("Service should have no data after failed JSON load")
	}
}

// testDataSource is a simple test implementation of DataSource
type testDataSource struct {
	data string
	err  error
}

func (t *testDataSource) Load(ctx context.Context) (io.ReadCloser, error) {
	if t.err != nil {
		return nil, t.err
	}
	return &stringReadCloser{data: t.data}, nil
}

func (t *testDataSource) Watch(ctx context.Context, callback func() error) error {
	return nil // No-op for tests
}

func (t *testDataSource) String() string {
	return "test-data-source"
}

// stringReadCloser implements io.ReadCloser for test data
type stringReadCloser struct {
	data string
	pos  int
}

func (s *stringReadCloser) Read(p []byte) (n int, err error) {
	if s.pos >= len(s.data) {
		return 0, io.EOF
	}

	n = copy(p, s.data[s.pos:])
	s.pos += n
	return n, nil
}

func (s *stringReadCloser) Close() error {
	return nil
}
