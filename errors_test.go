package orgdatacore

import (
	"errors"
	"testing"
)

func TestNotFoundError(t *testing.T) {
	err := NewNotFoundError("employee", "jsmith")

	// Test error message
	expected := `orgdatacore: employee not found: "jsmith"`
	if err.Error() != expected {
		t.Errorf("got %q, want %q", err.Error(), expected)
	}

	// Test errors.Is with ErrNotFound
	if !errors.Is(err, ErrNotFound) {
		t.Error("errors.Is should return true for ErrNotFound")
	}

	// Test errors.As
	var notFoundErr *NotFoundError
	if !errors.As(err, &notFoundErr) {
		t.Error("errors.As should work with *NotFoundError")
	}
	if notFoundErr.EntityType != "employee" {
		t.Errorf("EntityType = %q, want %q", notFoundErr.EntityType, "employee")
	}
	if notFoundErr.Key != "jsmith" {
		t.Errorf("Key = %q, want %q", notFoundErr.Key, "jsmith")
	}

	// Test Unwrap
	if unwrapped := err.Unwrap(); unwrapped != ErrNotFound {
		t.Errorf("Unwrap returned %v, want ErrNotFound", unwrapped)
	}
}

func TestConfigError(t *testing.T) {
	err := NewConfigError("bucket", "bucket name is required")

	// Test error message
	expected := "orgdatacore: invalid config for bucket: bucket name is required"
	if err.Error() != expected {
		t.Errorf("got %q, want %q", err.Error(), expected)
	}

	// Test errors.Is with ErrInvalidConfig
	if !errors.Is(err, ErrInvalidConfig) {
		t.Error("errors.Is should return true for ErrInvalidConfig")
	}

	// Test errors.As
	var configErr *ConfigError
	if !errors.As(err, &configErr) {
		t.Error("errors.As should work with *ConfigError")
	}
	if configErr.Field != "bucket" {
		t.Errorf("Field = %q, want %q", configErr.Field, "bucket")
	}

	// Test Unwrap
	if unwrapped := err.Unwrap(); unwrapped != ErrInvalidConfig {
		t.Errorf("Unwrap returned %v, want ErrInvalidConfig", unwrapped)
	}
}

func TestLoadError(t *testing.T) {
	underlying := errors.New("connection refused")
	err := NewLoadError("gs://bucket/path", underlying)

	// Test error message
	expected := "orgdatacore: failed to load from gs://bucket/path: connection refused"
	if err.Error() != expected {
		t.Errorf("got %q, want %q", err.Error(), expected)
	}

	// Test errors.Is with underlying error
	if !errors.Is(err, underlying) {
		t.Error("errors.Is should return true for underlying error")
	}

	// Test errors.As
	var loadErr *LoadError
	if !errors.As(err, &loadErr) {
		t.Error("errors.As should work with *LoadError")
	}
	if loadErr.Source != "gs://bucket/path" {
		t.Errorf("Source = %q, want %q", loadErr.Source, "gs://bucket/path")
	}

	// Test Unwrap
	if unwrapped := err.Unwrap(); unwrapped != underlying {
		t.Errorf("Unwrap returned %v, want underlying error", unwrapped)
	}
}

func TestSentinelErrors(t *testing.T) {
	tests := []struct {
		name     string
		err      error
		expected string
	}{
		{"ErrNoData", ErrNoData, "orgdatacore: no data loaded"},
		{"ErrNotFound", ErrNotFound, "orgdatacore: entity not found"},
		{"ErrGCSNotEnabled", ErrGCSNotEnabled, "orgdatacore: GCS support not enabled - build with -tags gcs"},
		{"ErrInvalidConfig", ErrInvalidConfig, "orgdatacore: invalid configuration"},
		{"ErrWatcherAlreadyRunning", ErrWatcherAlreadyRunning, "orgdatacore: watcher already running"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.err.Error() != tt.expected {
				t.Errorf("got %q, want %q", tt.err.Error(), tt.expected)
			}
		})
	}
}

func TestErrorWrapping(t *testing.T) {
	// Test that wrapped errors preserve the chain
	underlying := ErrNotFound
	loadErr := NewLoadError("test-source", underlying)

	// Should match ErrNotFound through the chain
	if !errors.Is(loadErr, ErrNotFound) {
		t.Error("errors.Is should traverse the error chain")
	}
}

