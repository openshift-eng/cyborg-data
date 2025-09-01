package orgdatacore

import (
	"context"
	"path/filepath"
	"testing"
)

// setupTestService creates a service loaded with test data
func setupTestService(t *testing.T) *Service {
	t.Helper()
	service := NewService()

	// Load test data
	testDataPath := filepath.Join("testdata", "test_org_data.json")
	fileSource := NewFileDataSource(testDataPath)

	ctx := context.Background()
	if err := service.LoadFromDataSource(ctx, fileSource); err != nil {
		t.Fatalf("Failed to load test data: %v", err)
	}

	return service
}

// TestNewService tests service creation
func TestNewService(t *testing.T) {
	service := NewService()
	if service == nil {
		t.Fatal("NewService() returned nil")
	}

	// Service should start with empty data
	if service.data != nil {
		t.Error("New service should have nil data")
	}
}

// TestServiceInterface ensures Service implements ServiceInterface
func TestServiceInterface(t *testing.T) {
	var _ ServiceInterface = (*Service)(nil)
}

// TestLoadFromDataSource tests data loading functionality
func TestLoadFromDataSource(t *testing.T) {
	tests := []struct {
		name         string
		dataFile     string
		expectError  bool
		expectedEmps int
		expectedOrgs int
	}{
		{
			name:         "valid data file",
			dataFile:     "test_org_data.json",
			expectError:  false,
			expectedEmps: 3,
			expectedOrgs: 2,
		},
		{
			name:        "nonexistent file",
			dataFile:    "nonexistent.json",
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			service := NewService()
			testDataPath := filepath.Join("testdata", tt.dataFile)
			fileSource := NewFileDataSource(testDataPath)

			err := service.LoadFromDataSource(context.Background(), fileSource)

			if tt.expectError {
				if err == nil {
					t.Error("Expected error but got none")
				}
				return
			}

			if err != nil {
				t.Fatalf("Unexpected error: %v", err)
			}

			// Check version info
			version := service.GetVersion()
			if version.EmployeeCount != tt.expectedEmps {
				t.Errorf("Expected %d employees, got %d", tt.expectedEmps, version.EmployeeCount)
			}
			if version.OrgCount != tt.expectedOrgs {
				t.Errorf("Expected %d orgs, got %d", tt.expectedOrgs, version.OrgCount)
			}
			if version.LoadTime.IsZero() {
				t.Error("LoadTime should be set after loading data")
			}
		})
	}
}

// TestGetVersion tests version information
func TestGetVersion(t *testing.T) {
	service := NewService()

	// Initially should have zero values
	version := service.GetVersion()
	if !version.LoadTime.IsZero() {
		t.Error("Expected zero time for initial version")
	}
	if version.EmployeeCount != 0 {
		t.Error("Expected zero employee count for initial version")
	}
	if version.OrgCount != 0 {
		t.Error("Expected zero org count for initial version")
	}

	// After loading data
	service = setupTestService(t)
	version = service.GetVersion()
	if version.EmployeeCount != 3 {
		t.Errorf("Expected 3 employees, got %d", version.EmployeeCount)
	}
	if version.OrgCount != 2 {
		t.Errorf("Expected 2 orgs, got %d", version.OrgCount)
	}
}
