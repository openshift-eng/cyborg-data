package orgdatacore

import (
	"context"
	"encoding/json"
	"testing"
)

// sampleEmployeeData returns a JSON string matching the Python test fixture.
func sampleEmployeeData() string {
	data := Data{
		Metadata: Metadata{GeneratedAt: "2025-01-01T10:00:00Z"},
		Lookups: Lookups{
			Employees: map[string]Employee{
				"jsmith": {
					UID: "jsmith", FullName: "John Smith", Email: "jsmith@example.com",
					JobTitle: "Senior Engineer", SlackUID: "U12345678", GitHubID: "jsmith-gh",
					ManagerUID: "adoe", IsPeopleManager: false,
				},
				"adoe": {
					UID: "adoe", FullName: "Alice Doe", Email: "adoe@example.com",
					JobTitle: "Team Lead", SlackUID: "U87654321", GitHubID: "adoe-gh",
					ManagerUID: "", IsPeopleManager: true,
				},
			},
			Teams: map[string]Team{},
			Orgs:  map[string]Org{},
		},
		Indexes: Indexes{
			Membership: MembershipIndex{
				MembershipIndex: map[string][]MembershipInfo{
					"jsmith": {},
					"adoe":   {},
				},
			},
			SlackIDMappings: SlackIDMappings{
				SlackUIDToUID: map[string]string{
					"U12345678": "jsmith",
					"U87654321": "adoe",
				},
			},
			GitHubIDMappings: GitHubIDMappings{
				GitHubIDToUID: map[string]string{
					"jsmith-gh": "jsmith",
					"adoe-gh":   "adoe",
				},
			},
		},
	}
	b, _ := json.Marshal(data)
	return string(b)
}

func loadRedactedJSON(t *testing.T, jsonData string, mode PIIMode) Data {
	t.Helper()
	inner := NewFakeDataSource(jsonData)
	source := NewRedactingDataSource(inner, mode)
	reader, err := source.Load(context.Background())
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	defer reader.Close()
	var result Data
	if err := json.NewDecoder(reader).Decode(&result); err != nil {
		t.Fatalf("Decode failed: %v", err)
	}
	return result
}

func TestRedactingDataSourceFullMode(t *testing.T) {
	t.Run("full mode returns unchanged data", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeFull)
		jsmith := result.Lookups.Employees["jsmith"]
		if jsmith.FullName != "John Smith" {
			t.Errorf("FullName = %q, want %q", jsmith.FullName, "John Smith")
		}
		if jsmith.Email != "jsmith@example.com" {
			t.Errorf("Email = %q, want %q", jsmith.Email, "jsmith@example.com")
		}
		if jsmith.SlackUID != "U12345678" {
			t.Errorf("SlackUID = %q, want %q", jsmith.SlackUID, "U12345678")
		}
		if jsmith.GitHubID != "jsmith-gh" {
			t.Errorf("GitHubID = %q, want %q", jsmith.GitHubID, "jsmith-gh")
		}
	})

	t.Run("full mode preserves indexes", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeFull)
		slackIndex := result.Indexes.SlackIDMappings.SlackUIDToUID
		if len(slackIndex) == 0 {
			t.Error("expected non-empty slack index in full mode")
		}
		if slackIndex["U12345678"] != "jsmith" {
			t.Errorf("SlackUIDToUID[U12345678] = %q, want %q", slackIndex["U12345678"], "jsmith")
		}
	})

	t.Run("full mode is default", func(t *testing.T) {
		inner := NewFakeDataSource(sampleEmployeeData())
		source := NewRedactingDataSource(inner, "")
		reader, err := source.Load(context.Background())
		if err != nil {
			t.Fatalf("Load failed: %v", err)
		}
		defer reader.Close()
		var result Data
		if err := json.NewDecoder(reader).Decode(&result); err != nil {
			t.Fatalf("Decode failed: %v", err)
		}
		if result.Lookups.Employees["jsmith"].FullName != "John Smith" {
			t.Error("expected full name to be preserved in default mode")
		}
	})
}

func TestRedactingDataSourceRedactedMode(t *testing.T) {
	t.Run("strips full_name", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		if result.Lookups.Employees["jsmith"].FullName != "[REDACTED]" {
			t.Errorf("FullName = %q, want [REDACTED]", result.Lookups.Employees["jsmith"].FullName)
		}
		if result.Lookups.Employees["adoe"].FullName != "[REDACTED]" {
			t.Errorf("FullName = %q, want [REDACTED]", result.Lookups.Employees["adoe"].FullName)
		}
	})

	t.Run("strips email", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		if result.Lookups.Employees["jsmith"].Email != "[REDACTED]" {
			t.Errorf("Email = %q, want [REDACTED]", result.Lookups.Employees["jsmith"].Email)
		}
		if result.Lookups.Employees["adoe"].Email != "[REDACTED]" {
			t.Errorf("Email = %q, want [REDACTED]", result.Lookups.Employees["adoe"].Email)
		}
	})

	t.Run("clears slack_uid", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		if result.Lookups.Employees["jsmith"].SlackUID != "" {
			t.Errorf("SlackUID = %q, want empty", result.Lookups.Employees["jsmith"].SlackUID)
		}
		if result.Lookups.Employees["adoe"].SlackUID != "" {
			t.Errorf("SlackUID = %q, want empty", result.Lookups.Employees["adoe"].SlackUID)
		}
	})

	t.Run("clears github_id", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		if result.Lookups.Employees["jsmith"].GitHubID != "" {
			t.Errorf("GitHubID = %q, want empty", result.Lookups.Employees["jsmith"].GitHubID)
		}
		if result.Lookups.Employees["adoe"].GitHubID != "" {
			t.Errorf("GitHubID = %q, want empty", result.Lookups.Employees["adoe"].GitHubID)
		}
	})

	t.Run("preserves non-PII fields", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		jsmith := result.Lookups.Employees["jsmith"]
		if jsmith.UID != "jsmith" {
			t.Errorf("UID = %q, want %q", jsmith.UID, "jsmith")
		}
		if jsmith.JobTitle != "Senior Engineer" {
			t.Errorf("JobTitle = %q, want %q", jsmith.JobTitle, "Senior Engineer")
		}
		if jsmith.ManagerUID != "adoe" {
			t.Errorf("ManagerUID = %q, want %q", jsmith.ManagerUID, "adoe")
		}
		if jsmith.IsPeopleManager != false {
			t.Error("IsPeopleManager should be false")
		}
	})

	t.Run("preserves metadata", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		if result.Metadata.GeneratedAt != "2025-01-01T10:00:00Z" {
			t.Errorf("GeneratedAt = %q, want %q", result.Metadata.GeneratedAt, "2025-01-01T10:00:00Z")
		}
	})
}

func TestRedactingDataSourceIndexes(t *testing.T) {
	t.Run("clears slack index", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		slackIndex := result.Indexes.SlackIDMappings.SlackUIDToUID
		if len(slackIndex) != 0 {
			t.Errorf("expected empty slack index, got %d entries", len(slackIndex))
		}
	})

	t.Run("clears github index", func(t *testing.T) {
		result := loadRedactedJSON(t, sampleEmployeeData(), PIIModeRedacted)
		githubIndex := result.Indexes.GitHubIDMappings.GitHubIDToUID
		if len(githubIndex) != 0 {
			t.Errorf("expected empty github index, got %d entries", len(githubIndex))
		}
	})
}

func TestRedactingDataSourceEdgeCases(t *testing.T) {
	t.Run("empty employees", func(t *testing.T) {
		data := Data{
			Lookups: Lookups{Employees: map[string]Employee{}},
			Indexes: Indexes{
				SlackIDMappings:  SlackIDMappings{SlackUIDToUID: map[string]string{}},
				GitHubIDMappings: GitHubIDMappings{GitHubIDToUID: map[string]string{}},
			},
		}
		b, _ := json.Marshal(data)
		result := loadRedactedJSON(t, string(b), PIIModeRedacted)
		if len(result.Lookups.Employees) != 0 {
			t.Error("expected empty employees map")
		}
	})

	t.Run("missing indexes", func(t *testing.T) {
		data := Data{
			Lookups: Lookups{
				Employees: map[string]Employee{
					"jsmith": {UID: "jsmith", FullName: "John", Email: "j@x.com"},
				},
			},
		}
		b, _ := json.Marshal(data)
		result := loadRedactedJSON(t, string(b), PIIModeRedacted)
		if result.Lookups.Employees["jsmith"].FullName != "[REDACTED]" {
			t.Errorf("FullName = %q, want [REDACTED]", result.Lookups.Employees["jsmith"].FullName)
		}
	})
}

func TestRedactingDataSourceStr(t *testing.T) {
	inner := NewFakeDataSource(sampleEmployeeData())

	t.Run("full mode string", func(t *testing.T) {
		source := NewRedactingDataSource(inner, PIIModeFull)
		if got := source.String(); got != "fake-data-source" {
			t.Errorf("String() = %q, want %q", got, "fake-data-source")
		}
	})

	t.Run("redacted mode string", func(t *testing.T) {
		source := NewRedactingDataSource(inner, PIIModeRedacted)
		expected := "fake-data-source [PII redacted]"
		if got := source.String(); got != expected {
			t.Errorf("String() = %q, want %q", got, expected)
		}
	})
}

func TestRedactingDataSourceWithService(t *testing.T) {
	t.Run("service loads redacted data", func(t *testing.T) {
		inner := NewFakeDataSource(sampleEmployeeData())
		source := NewRedactingDataSource(inner, PIIModeRedacted)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		emp := service.GetEmployeeByUID("jsmith")
		if emp == nil {
			t.Fatal("expected employee, got nil")
		}
		if emp.FullName != "[REDACTED]" {
			t.Errorf("FullName = %q, want [REDACTED]", emp.FullName)
		}
		if emp.Email != "[REDACTED]" {
			t.Errorf("Email = %q, want [REDACTED]", emp.Email)
		}
		if emp.SlackUID != "" {
			t.Errorf("SlackUID = %q, want empty", emp.SlackUID)
		}
	})

	t.Run("service loads full data", func(t *testing.T) {
		inner := NewFakeDataSource(sampleEmployeeData())
		source := NewRedactingDataSource(inner, PIIModeFull)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		emp := service.GetEmployeeByUID("jsmith")
		if emp == nil {
			t.Fatal("expected employee, got nil")
		}
		if emp.FullName != "John Smith" {
			t.Errorf("FullName = %q, want %q", emp.FullName, "John Smith")
		}
		if emp.Email != "jsmith@example.com" {
			t.Errorf("Email = %q, want %q", emp.Email, "jsmith@example.com")
		}
	})

	t.Run("slack lookup disabled in redacted mode", func(t *testing.T) {
		inner := NewFakeDataSource(sampleEmployeeData())
		source := NewRedactingDataSource(inner, PIIModeRedacted)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		if emp := service.GetEmployeeBySlackID("U12345678"); emp != nil {
			t.Error("expected nil for slack lookup in redacted mode")
		}
	})

	t.Run("github lookup disabled in redacted mode", func(t *testing.T) {
		inner := NewFakeDataSource(sampleEmployeeData())
		source := NewRedactingDataSource(inner, PIIModeRedacted)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		if emp := service.GetEmployeeByGitHubID("jsmith-gh"); emp != nil {
			t.Error("expected nil for github lookup in redacted mode")
		}
	})
}
