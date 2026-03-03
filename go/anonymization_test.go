package orgdatacore

import (
	"context"
	"encoding/json"
	"regexp"
	"testing"
)

var noncePattern = regexp.MustCompile(`^HUMAN-[a-f0-9]{8}$`)
var slackNoncePattern = regexp.MustCompile(`^SLACK-[a-f0-9]{8}$`)
var githubNoncePattern = regexp.MustCompile(`^GITHUB-[a-f0-9]{8}$`)

// sampleAnonymizationData returns JSON with employees, groups, and indexes.
func sampleAnonymizationData() string {
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
			Teams: map[string]Team{
				"test-squad": {
					UID: "test-squad", Name: "Test Squad", TabName: "test-squad",
					Description: "A test team", Type: "team",
					Group: Group{
						ResolvedPeopleUIDList: []string{"jsmith", "adoe"},
						Roles: []RoleInfo{
							{People: []string{"adoe"}, Roles: []string{"lead"}},
						},
					},
				},
			},
			Orgs: map[string]Org{
				"test-org": {
					UID: "test-org", Name: "Test Org", TabName: "test-org",
					Description: "A test org", Type: "org",
					Group: Group{
						ResolvedPeopleUIDList: []string{"jsmith", "adoe"},
						Roles:                 []RoleInfo{},
					},
				},
			},
			Pillars:    map[string]Pillar{},
			TeamGroups: map[string]TeamGroup{},
		},
		Indexes: Indexes{
			Membership: MembershipIndex{
				MembershipIndex: map[string][]MembershipInfo{
					"jsmith": {{Name: "test-squad", Type: "team"}},
					"adoe":   {{Name: "test-squad", Type: "team"}},
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

func loadAnonymizedJSON(t *testing.T, jsonData string, mode PIIMode) (Data, *AnonymizingDataSource) {
	t.Helper()
	inner := NewFakeDataSource(jsonData)
	source := NewAnonymizingDataSource(inner, mode)
	reader, err := source.Load(context.Background())
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	defer reader.Close()
	var result Data
	if err := json.NewDecoder(reader).Decode(&result); err != nil {
		t.Fatalf("Decode failed: %v", err)
	}
	return result, source
}

func TestAnonymizingDataSourceFullMode(t *testing.T) {
	t.Run("full mode returns unchanged data", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeFull)
		jsmith := result.Lookups.Employees["jsmith"]
		if jsmith.FullName != "John Smith" {
			t.Errorf("FullName = %q, want %q", jsmith.FullName, "John Smith")
		}
		if jsmith.Email != "jsmith@example.com" {
			t.Errorf("Email = %q, want %q", jsmith.Email, "jsmith@example.com")
		}
		if jsmith.UID != "jsmith" {
			t.Errorf("UID = %q, want %q", jsmith.UID, "jsmith")
		}
	})

	t.Run("full mode is default", func(t *testing.T) {
		inner := NewFakeDataSource(sampleAnonymizationData())
		source := NewAnonymizingDataSource(inner, "")
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

func TestAnonymizingDataSourceAnonymizedMode(t *testing.T) {
	t.Run("UIDs match nonce pattern", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		for key, emp := range result.Lookups.Employees {
			if !noncePattern.MatchString(key) {
				t.Errorf("employee key %q doesn't match nonce pattern", key)
			}
			if !noncePattern.MatchString(emp.UID) {
				t.Errorf("employee UID %q doesn't match nonce pattern", emp.UID)
			}
			if emp.UID != key {
				t.Errorf("employee UID %q doesn't match key %q", emp.UID, key)
			}
		}
	})

	t.Run("names anonymized", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		for _, emp := range result.Lookups.Employees {
			if emp.FullName != "[ANONYMIZED]" {
				t.Errorf("FullName = %q, want [ANONYMIZED]", emp.FullName)
			}
		}
	})

	t.Run("emails anonymized", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		for _, emp := range result.Lookups.Employees {
			if emp.Email != "[ANONYMIZED]" {
				t.Errorf("Email = %q, want [ANONYMIZED]", emp.Email)
			}
		}
	})

	t.Run("slack_uid anonymized with nonce", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		for _, emp := range result.Lookups.Employees {
			if !slackNoncePattern.MatchString(emp.SlackUID) {
				t.Errorf("SlackUID = %q, want SLACK-<hex> nonce", emp.SlackUID)
			}
		}
	})

	t.Run("github_id anonymized with nonce", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		for _, emp := range result.Lookups.Employees {
			if !githubNoncePattern.MatchString(emp.GitHubID) {
				t.Errorf("GitHubID = %q, want GITHUB-<hex> nonce", emp.GitHubID)
			}
		}
	})

	t.Run("manager UID consistent", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		employees := result.Lookups.Employees

		// Find the employee with a non-empty manager_uid
		var managedCount int
		for _, emp := range employees {
			if emp.ManagerUID != "" {
				managedCount++
				if !noncePattern.MatchString(emp.ManagerUID) {
					t.Errorf("manager UID %q doesn't match nonce pattern", emp.ManagerUID)
				}
				// Manager nonce should be a key in the employees map
				if _, exists := employees[emp.ManagerUID]; !exists {
					t.Errorf("manager nonce %q not found in employees", emp.ManagerUID)
				}
			}
		}
		if managedCount != 1 {
			t.Errorf("expected exactly 1 managed employee, got %d", managedCount)
		}
	})

	t.Run("non-PII fields preserved", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		jobTitles := make(map[string]bool)
		for _, emp := range result.Lookups.Employees {
			jobTitles[emp.JobTitle] = true
		}
		if !jobTitles["Senior Engineer"] {
			t.Error("expected 'Senior Engineer' job title to be preserved")
		}
		if !jobTitles["Team Lead"] {
			t.Error("expected 'Team Lead' job title to be preserved")
		}
	})

	t.Run("metadata preserved", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		if result.Metadata.GeneratedAt != "2025-01-01T10:00:00Z" {
			t.Errorf("GeneratedAt = %q, want %q", result.Metadata.GeneratedAt, "2025-01-01T10:00:00Z")
		}
	})
}

func TestAnonymizingDataSourceIndexes(t *testing.T) {
	t.Run("membership index re-keyed", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		membershipIndex := result.Indexes.Membership.MembershipIndex

		for key := range membershipIndex {
			if !noncePattern.MatchString(key) {
				t.Errorf("membership key %q doesn't match nonce pattern", key)
			}
		}
		if _, exists := membershipIndex["jsmith"]; exists {
			t.Error("original UID 'jsmith' should not be in membership index")
		}
		if _, exists := membershipIndex["adoe"]; exists {
			t.Error("original UID 'adoe' should not be in membership index")
		}
	})

	t.Run("slack index remapped with nonces", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		slackIndex := result.Indexes.SlackIDMappings.SlackUIDToUID
		if len(slackIndex) != 2 {
			t.Fatalf("expected 2 slack index entries, got %d", len(slackIndex))
		}
		for slackNonce, uidNonce := range slackIndex {
			if !slackNoncePattern.MatchString(slackNonce) {
				t.Errorf("slack index key %q doesn't match SLACK nonce pattern", slackNonce)
			}
			if !noncePattern.MatchString(uidNonce) {
				t.Errorf("slack index value %q doesn't match HUMAN nonce pattern", uidNonce)
			}
		}
		// Original Slack IDs should be gone
		if _, exists := slackIndex["U12345678"]; exists {
			t.Error("original Slack ID 'U12345678' should not be in slack index")
		}
	})

	t.Run("github index remapped with nonces", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		githubIndex := result.Indexes.GitHubIDMappings.GitHubIDToUID
		if len(githubIndex) != 2 {
			t.Fatalf("expected 2 github index entries, got %d", len(githubIndex))
		}
		for githubNonce, uidNonce := range githubIndex {
			if !githubNoncePattern.MatchString(githubNonce) {
				t.Errorf("github index key %q doesn't match GITHUB nonce pattern", githubNonce)
			}
			if !noncePattern.MatchString(uidNonce) {
				t.Errorf("github index value %q doesn't match HUMAN nonce pattern", uidNonce)
			}
		}
		// Original GitHub IDs should be gone
		if _, exists := githubIndex["jsmith-gh"]; exists {
			t.Error("original GitHub ID 'jsmith-gh' should not be in github index")
		}
	})
}

func TestAnonymizingDataSourceGroups(t *testing.T) {
	t.Run("team resolved_people remapped", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		people := result.Lookups.Teams["test-squad"].Group.ResolvedPeopleUIDList
		if len(people) != 2 {
			t.Fatalf("expected 2 people, got %d", len(people))
		}
		for _, p := range people {
			if !noncePattern.MatchString(p) {
				t.Errorf("person %q doesn't match nonce pattern", p)
			}
		}
	})

	t.Run("org resolved_people remapped", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		people := result.Lookups.Orgs["test-org"].Group.ResolvedPeopleUIDList
		if len(people) != 2 {
			t.Fatalf("expected 2 people, got %d", len(people))
		}
		for _, p := range people {
			if !noncePattern.MatchString(p) {
				t.Errorf("person %q doesn't match nonce pattern", p)
			}
		}
	})

	t.Run("roles people remapped", func(t *testing.T) {
		result, _ := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		roles := result.Lookups.Teams["test-squad"].Group.Roles
		if len(roles) != 1 {
			t.Fatalf("expected 1 role, got %d", len(roles))
		}
		for _, person := range roles[0].People {
			if !noncePattern.MatchString(person) {
				t.Errorf("role person %q doesn't match nonce pattern", person)
			}
		}
	})
}

func TestAnonymizingDataSourceLookupAPI(t *testing.T) {
	t.Run("resolve returns real UID", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		nonce, ok := source.AnonymizeUID("jsmith")
		if !ok {
			t.Fatal("expected AnonymizeUID to succeed for jsmith")
		}
		uid, ok := source.Resolve(nonce)
		if !ok || uid != "jsmith" {
			t.Errorf("Resolve(%q) = %q, %v; want %q, true", nonce, uid, ok, "jsmith")
		}
	})

	t.Run("anonymize_uid", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		nonce, ok := source.AnonymizeUID("adoe")
		if !ok {
			t.Fatal("expected AnonymizeUID to succeed for adoe")
		}
		if !noncePattern.MatchString(nonce) {
			t.Errorf("nonce %q doesn't match pattern", nonce)
		}
	})

	t.Run("lookup_by_name case insensitive", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		nonce1, ok1 := source.LookupByName("John Smith")
		nonce2, ok2 := source.LookupByName("john smith")
		nonce3, ok3 := source.LookupByName("JOHN SMITH")
		if !ok1 || !ok2 || !ok3 {
			t.Fatal("expected all LookupByName calls to succeed")
		}
		if nonce1 != nonce2 || nonce1 != nonce3 {
			t.Errorf("expected same nonce for all cases, got %q, %q, %q", nonce1, nonce2, nonce3)
		}
	})

	t.Run("get_display_name", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		nonce, _ := source.AnonymizeUID("jsmith")
		display, ok := source.GetDisplayName(nonce)
		if !ok {
			t.Fatal("expected GetDisplayName to succeed")
		}
		if display != "John Smith (jsmith)" {
			t.Errorf("GetDisplayName = %q, want %q", display, "John Smith (jsmith)")
		}
	})

	t.Run("unknown nonce returns false", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		_, ok := source.Resolve("HUMAN-00000000")
		if ok {
			t.Error("expected Resolve to return false for unknown nonce")
		}
		_, ok = source.GetDisplayName("HUMAN-00000000")
		if ok {
			t.Error("expected GetDisplayName to return false for unknown nonce")
		}
	})

	t.Run("unknown uid returns false", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		_, ok := source.AnonymizeUID("nonexistent")
		if ok {
			t.Error("expected AnonymizeUID to return false for unknown UID")
		}
	})

	t.Run("uid_to_nonce_map", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		mapping := source.UIDToNonceMap()
		if len(mapping) != 2 {
			t.Errorf("expected 2 entries, got %d", len(mapping))
		}
		if _, ok := mapping["jsmith"]; !ok {
			t.Error("expected 'jsmith' in UIDToNonceMap")
		}
		if _, ok := mapping["adoe"]; !ok {
			t.Error("expected 'adoe' in UIDToNonceMap")
		}
	})

	t.Run("name_to_nonce_map", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		mapping := source.NameToNonceMap()
		if _, ok := mapping["john smith"]; !ok {
			t.Error("expected 'john smith' in NameToNonceMap")
		}
		if _, ok := mapping["alice doe"]; !ok {
			t.Error("expected 'alice doe' in NameToNonceMap")
		}
	})

	t.Run("slack_id_to_nonce_map", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		mapping := source.SlackIDToNonceMap()
		if len(mapping) != 2 {
			t.Errorf("expected 2 entries, got %d", len(mapping))
		}
		if nonce, ok := mapping["U12345678"]; !ok {
			t.Error("expected 'U12345678' in SlackIDToNonceMap")
		} else if !slackNoncePattern.MatchString(nonce) {
			t.Errorf("slack nonce %q doesn't match SLACK pattern", nonce)
		}
		if nonce, ok := mapping["U87654321"]; !ok {
			t.Error("expected 'U87654321' in SlackIDToNonceMap")
		} else if !slackNoncePattern.MatchString(nonce) {
			t.Errorf("slack nonce %q doesn't match SLACK pattern", nonce)
		}
	})

	t.Run("github_id_to_nonce_map", func(t *testing.T) {
		_, source := loadAnonymizedJSON(t, sampleAnonymizationData(), PIIModeAnonymized)
		mapping := source.GitHubIDToNonceMap()
		if len(mapping) != 2 {
			t.Errorf("expected 2 entries, got %d", len(mapping))
		}
		if nonce, ok := mapping["jsmith-gh"]; !ok {
			t.Error("expected 'jsmith-gh' in GitHubIDToNonceMap")
		} else if !githubNoncePattern.MatchString(nonce) {
			t.Errorf("github nonce %q doesn't match GITHUB pattern", nonce)
		}
		if nonce, ok := mapping["adoe-gh"]; !ok {
			t.Error("expected 'adoe-gh' in GitHubIDToNonceMap")
		} else if !githubNoncePattern.MatchString(nonce) {
			t.Errorf("github nonce %q doesn't match GITHUB pattern", nonce)
		}
	})
}

func TestAnonymizingDataSourceEphemeral(t *testing.T) {
	t.Run("nonces regenerated on reload", func(t *testing.T) {
		inner := NewFakeDataSource(sampleAnonymizationData())
		source := NewAnonymizingDataSource(inner, PIIModeAnonymized)

		// First load
		reader1, err := source.Load(context.Background())
		if err != nil {
			t.Fatalf("first Load failed: %v", err)
		}
		reader1.Close()
		nonce1, ok := source.AnonymizeUID("jsmith")
		if !ok {
			t.Fatal("expected AnonymizeUID to succeed after first load")
		}

		// Second load — nonces should regenerate
		reader2, err := source.Load(context.Background())
		if err != nil {
			t.Fatalf("second Load failed: %v", err)
		}
		reader2.Close()
		nonce2, ok := source.AnonymizeUID("jsmith")
		if !ok {
			t.Fatal("expected AnonymizeUID to succeed after second load")
		}

		// Both should be valid nonces
		if !noncePattern.MatchString(nonce1) {
			t.Errorf("nonce1 %q doesn't match pattern", nonce1)
		}
		if !noncePattern.MatchString(nonce2) {
			t.Errorf("nonce2 %q doesn't match pattern", nonce2)
		}
		if nonce1 == nonce2 {
			t.Errorf("expected different nonces across loads, got same nonce %q", nonce1)
		}
	})
}

func TestAnonymizingDataSourceStr(t *testing.T) {
	inner := NewFakeDataSource(sampleAnonymizationData())

	t.Run("full mode string", func(t *testing.T) {
		source := NewAnonymizingDataSource(inner, PIIModeFull)
		if got := source.String(); got != "fake-data-source" {
			t.Errorf("String() = %q, want %q", got, "fake-data-source")
		}
	})

	t.Run("anonymized mode string", func(t *testing.T) {
		source := NewAnonymizingDataSource(inner, PIIModeAnonymized)
		expected := "fake-data-source [PII anonymized]"
		if got := source.String(); got != expected {
			t.Errorf("String() = %q, want %q", got, expected)
		}
	})
}

func TestAnonymizingDataSourceEdgeCases(t *testing.T) {
	t.Run("empty employees", func(t *testing.T) {
		data := Data{
			Lookups: Lookups{Employees: map[string]Employee{}},
			Indexes: Indexes{
				SlackIDMappings:  SlackIDMappings{SlackUIDToUID: map[string]string{}},
				GitHubIDMappings: GitHubIDMappings{GitHubIDToUID: map[string]string{}},
			},
		}
		b, _ := json.Marshal(data)
		result, _ := loadAnonymizedJSON(t, string(b), PIIModeAnonymized)
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
		result, _ := loadAnonymizedJSON(t, string(b), PIIModeAnonymized)
		if len(result.Lookups.Employees) != 1 {
			t.Fatalf("expected 1 employee, got %d", len(result.Lookups.Employees))
		}
		for _, emp := range result.Lookups.Employees {
			if emp.FullName != "[ANONYMIZED]" {
				t.Errorf("FullName = %q, want [ANONYMIZED]", emp.FullName)
			}
		}
	})
}

func TestAnonymizingDataSourceWithService(t *testing.T) {
	t.Run("service loads anonymized data", func(t *testing.T) {
		inner := NewFakeDataSource(sampleAnonymizationData())
		source := NewAnonymizingDataSource(inner, PIIModeAnonymized)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		nonce, ok := source.AnonymizeUID("jsmith")
		if !ok {
			t.Fatal("expected AnonymizeUID to succeed")
		}

		emp := service.GetEmployeeByUID(nonce)
		if emp == nil {
			t.Fatal("expected employee, got nil")
		}
		if emp.FullName != "[ANONYMIZED]" {
			t.Errorf("FullName = %q, want [ANONYMIZED]", emp.FullName)
		}
		if emp.Email != "[ANONYMIZED]" {
			t.Errorf("Email = %q, want [ANONYMIZED]", emp.Email)
		}
		if !slackNoncePattern.MatchString(emp.SlackUID) {
			t.Errorf("SlackUID = %q, want SLACK-<hex> nonce", emp.SlackUID)
		}
	})

	t.Run("slack lookup works with nonce", func(t *testing.T) {
		inner := NewFakeDataSource(sampleAnonymizationData())
		source := NewAnonymizingDataSource(inner, PIIModeAnonymized)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		// Original Slack ID should not work
		if emp := service.GetEmployeeBySlackID("U12345678"); emp != nil {
			t.Error("expected nil for original slack ID lookup")
		}

		// Slack nonce should work
		slackNonce := source.SlackIDToNonceMap()["U12345678"]
		if slackNonce == "" {
			t.Fatal("expected slack nonce for U12345678")
		}
		emp := service.GetEmployeeBySlackID(slackNonce)
		if emp == nil {
			t.Fatal("expected employee for slack nonce lookup, got nil")
		}
		if emp.FullName != "[ANONYMIZED]" {
			t.Errorf("FullName = %q, want [ANONYMIZED]", emp.FullName)
		}
	})

	t.Run("github lookup works with nonce", func(t *testing.T) {
		inner := NewFakeDataSource(sampleAnonymizationData())
		source := NewAnonymizingDataSource(inner, PIIModeAnonymized)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		// Original GitHub ID should not work
		if emp := service.GetEmployeeByGitHubID("jsmith-gh"); emp != nil {
			t.Error("expected nil for original github ID lookup")
		}

		// GitHub nonce should work
		githubNonce := source.GitHubIDToNonceMap()["jsmith-gh"]
		if githubNonce == "" {
			t.Fatal("expected github nonce for jsmith-gh")
		}
		emp := service.GetEmployeeByGitHubID(githubNonce)
		if emp == nil {
			t.Fatal("expected employee for github nonce lookup, got nil")
		}
		if emp.FullName != "[ANONYMIZED]" {
			t.Errorf("FullName = %q, want [ANONYMIZED]", emp.FullName)
		}
	})

	t.Run("original UID not found", func(t *testing.T) {
		inner := NewFakeDataSource(sampleAnonymizationData())
		source := NewAnonymizingDataSource(inner, PIIModeAnonymized)

		service := NewService()
		if err := service.LoadFromDataSource(context.Background(), source); err != nil {
			t.Fatalf("LoadFromDataSource failed: %v", err)
		}

		if emp := service.GetEmployeeByUID("jsmith"); emp != nil {
			t.Error("expected nil for original UID lookup in anonymized mode")
		}
	})
}
