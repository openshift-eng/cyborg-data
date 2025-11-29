package orgdatacore

import (
	"strings"
	"testing"
)

func TestGetVersionInfo(t *testing.T) {
	info := GetVersionInfo()

	// Version should be set (either "dev" or an actual version)
	if info.Version == "" {
		t.Error("Version should not be empty")
	}

	// GitCommit should be set
	if info.GitCommit == "" {
		t.Error("GitCommit should not be empty")
	}
}

func TestVersionInfoString(t *testing.T) {
	info := VersionInfo{
		Version:   "0.2.1",
		GitCommit: "abc1234567890",
		BuildDate: "2025-01-01T00:00:00Z",
		GoVersion: "go1.23.0",
	}

	str := info.String()

	if !strings.Contains(str, "0.2.1") {
		t.Error("String should contain version")
	}
	if !strings.Contains(str, "abc1234") {
		t.Error("String should contain short commit (7 chars)")
	}
	if !strings.Contains(str, "2025-01-01T00:00:00Z") {
		t.Error("String should contain build date")
	}
	if !strings.Contains(str, "go1.23.0") {
		t.Error("String should contain Go version")
	}
}

func TestVersionInfoShort(t *testing.T) {
	info := VersionInfo{
		Version: "0.3.2",
	}

	if info.Short() != "0.3.2" {
		t.Errorf("Short() = %q, want %q", info.Short(), "0.3.2")
	}
}

func TestGetLibraryVersion(t *testing.T) {
	version := GetLibraryVersion()
	if version == "" {
		t.Error("GetLibraryVersion() should not return empty string")
	}
}

func TestShortCommit(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"abc1234567890", "abc1234"},
		{"abc", "abc"},
		{"ab", "ab"},
		{"", ""},
		{"1234567", "1234567"},
		{"12345678", "1234567"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := shortCommit(tt.input)
			if result != tt.expected {
				t.Errorf("shortCommit(%q) = %q, want %q", tt.input, result, tt.expected)
			}
		})
	}
}
