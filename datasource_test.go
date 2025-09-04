package orgdatacore

import (
	"context"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestFileDataSource tests the FileDataSource implementation
func TestFileDataSource(t *testing.T) {
	// Test with existing test data
	testDataPath := filepath.Join("testdata", "test_org_data.json")

	tests := []struct {
		name        string
		filePaths   []string
		expectError bool
	}{
		{
			name:        "valid single file",
			filePaths:   []string{testDataPath},
			expectError: false,
		},
		{
			name:        "multiple files (uses last)",
			filePaths:   []string{"nonexistent.json", testDataPath},
			expectError: false,
		},
		{
			name:        "nonexistent file",
			filePaths:   []string{"nonexistent.json"},
			expectError: true,
		},
		{
			name:        "empty file paths",
			filePaths:   []string{},
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			source := NewFileDataSource(tt.filePaths...)

			reader, err := source.Load(context.Background())

			if tt.expectError {
				if err == nil {
					t.Error("Expected error but got none")
				}
				if reader != nil {
					reader.Close()
					t.Error("Expected nil reader on error")
				}
				return
			}

			if err != nil {
				t.Errorf("Unexpected error: %v", err)
				return
			}

			if reader == nil {
				t.Error("Expected reader but got nil")
				return
			}
			defer reader.Close()

			// Read some data to verify it's valid
			data, err := io.ReadAll(reader)
			if err != nil {
				t.Errorf("Failed to read data: %v", err)
			}

			if len(data) == 0 {
				t.Error("Expected data but got empty content")
			}

			// Should be valid JSON (starts with { or [)
			content := strings.TrimSpace(string(data))
			if !strings.HasPrefix(content, "{") && !strings.HasPrefix(content, "[") {
				t.Error("Data doesn't appear to be valid JSON")
			}
		})
	}
}

// TestFileDataSourceString tests the String() method
func TestFileDataSourceString(t *testing.T) {
	tests := []struct {
		name      string
		filePaths []string
		contains  string
	}{
		{
			name:      "single file",
			filePaths: []string{"test.json"},
			contains:  "test.json",
		},
		{
			name:      "multiple files",
			filePaths: []string{"file1.json", "file2.json"},
			contains:  "files:",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			source := NewFileDataSource(tt.filePaths...)
			result := source.String()

			if !strings.Contains(result, tt.contains) {
				t.Errorf("String() = %q, expected to contain %q", result, tt.contains)
			}
		})
	}
}

// TestFileDataSourceWatch tests the file watching functionality
func TestFileDataSourceWatch(t *testing.T) {
	// Create a temporary file for testing
	tmpDir := t.TempDir()
	tmpFile := filepath.Join(tmpDir, "test_watch.json")

	// Write initial content
	initialContent := `{"test": "data"}`
	err := os.WriteFile(tmpFile, []byte(initialContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create test file: %v", err)
	}

	source := NewFileDataSource(tmpFile)
	source.PollInterval = 50 * time.Millisecond

	// Test watch functionality
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	callbackCalled := make(chan bool, 1)
	callback := func() error {
		callbackCalled <- true
		return nil
	}

	err = source.Watch(ctx, callback)
	if err != nil {
		t.Errorf("Watch() returned error: %v", err)
	}

	// Modify the file
	go func() {
		time.Sleep(100 * time.Millisecond)
		os.WriteFile(tmpFile, []byte(`{"test": "modified"}`), 0644)
	}()

	// Wait for callback (with timeout)
	select {
	case <-callbackCalled:
		// Success - callback was called
	case <-time.After(2 * time.Second):
		t.Fatalf("File watch callback not called within timeout")
	}
}

// TestGCSDataSourceStub tests the GCS data source stub behavior
func TestGCSDataSourceStub(t *testing.T) {
	config := GCSConfig{
		Bucket:        "test-bucket",
		ObjectPath:    "test/path.json",
		ProjectID:     "test-project",
		CheckInterval: 5 * time.Minute,
	}

	source := NewGCSDataSource(config)

	// String method should work
	description := source.String()
	if !strings.Contains(description, "test-bucket") {
		t.Errorf("String() = %q, expected to contain 'test-bucket'", description)
	}

	// Load should return an error (stub implementation)
	_, err := source.Load(context.Background())
	if err == nil {
		t.Error("Expected error from GCS stub Load() method")
	}

	// Watch should return an error (stub implementation)
	err = source.Watch(context.Background(), func() error { return nil })
	if err == nil {
		t.Error("Expected error from GCS stub Watch() method")
	}
}

// TestDataSourceIntegrationWithService tests DataSource integration
func TestDataSourceIntegrationWithService(t *testing.T) {
	service := NewService()

	// Test with file data source
	testDataPath := filepath.Join("testdata", "test_org_data.json")
	fileSource := NewFileDataSource(testDataPath)

	err := service.LoadFromDataSource(context.Background(), fileSource)
	if err != nil {
		t.Fatalf("Failed to load from FileDataSource: %v", err)
	}

	// Verify data was loaded correctly
	version := service.GetVersion()
	if version.EmployeeCount == 0 {
		t.Error("No employees loaded from data source")
	}

	// Verify queries work
	emp := service.GetEmployeeByUID("jsmith")
	if emp == nil {
		t.Error("Employee lookup failed after loading from data source")
	}
}
