package orgdatacore

import (
	"context"
	"encoding/json"
	"testing"

	testingsupport "github.com/openshift-eng/cyborg-data/go/internal/testing"
)

// TestFakeGCSClient tests the fake GCS client implementation.
func TestFakeGCSClient(t *testing.T) {
	client := testingsupport.NewFakeGCSClient()
	if client == nil {
		t.Fatal("NewFakeGCSClient returned nil")
	}

	// Add a bucket
	bucket := client.AddBucket("test-bucket")
	if bucket == nil {
		t.Fatal("AddBucket returned nil")
	}
	if bucket.Name != "test-bucket" {
		t.Errorf("Expected bucket name 'test-bucket', got %q", bucket.Name)
	}

	// Get the bucket
	retrieved, ok := client.GetBucket("test-bucket")
	if !ok {
		t.Fatal("GetBucket returned false for existing bucket")
	}
	if retrieved != bucket {
		t.Error("GetBucket returned different bucket instance")
	}

	// Get non-existent bucket
	_, ok = client.GetBucket("nonexistent")
	if ok {
		t.Error("GetBucket should return false for non-existent bucket")
	}
}

// TestFakeBucket tests the fake bucket implementation.
func TestFakeBucket(t *testing.T) {
	bucket := testingsupport.NewFakeBucket("my-bucket")
	if bucket.Name != "my-bucket" {
		t.Errorf("Expected bucket name 'my-bucket', got %q", bucket.Name)
	}

	// Add a blob
	content := []byte(`{"key": "value"}`)
	blob := bucket.AddBlob("path/to/file.json", content)
	if blob == nil {
		t.Fatal("AddBlob returned nil")
	}
	if blob.Name != "path/to/file.json" {
		t.Errorf("Expected blob name 'path/to/file.json', got %q", blob.Name)
	}
	if string(blob.Content) != string(content) {
		t.Errorf("Expected content %q, got %q", content, blob.Content)
	}
	if blob.Generation != 1 {
		t.Errorf("Expected generation 1, got %d", blob.Generation)
	}

	// Get the blob
	retrieved, ok := bucket.GetBlob("path/to/file.json")
	if !ok {
		t.Fatal("GetBlob returned false for existing blob")
	}
	if retrieved != blob {
		t.Error("GetBlob returned different blob instance")
	}

	// Get non-existent blob
	_, ok = bucket.GetBlob("nonexistent")
	if ok {
		t.Error("GetBlob should return false for non-existent blob")
	}
}

// TestFakeBlobUpdate tests updating blob content.
func TestFakeBlobUpdate(t *testing.T) {
	bucket := testingsupport.NewFakeBucket("test-bucket")
	bucket.AddBlob("data.json", []byte("original"))

	// Update the blob
	err := bucket.UpdateBlob("data.json", []byte("updated"))
	if err != nil {
		t.Fatalf("UpdateBlob failed: %v", err)
	}

	// Check updated content
	blob, ok := bucket.GetBlob("data.json")
	if !ok {
		t.Fatal("GetBlob returned false after update")
	}
	if string(blob.Content) != "updated" {
		t.Errorf("Expected content 'updated', got %q", blob.Content)
	}
	if blob.Generation != 2 {
		t.Errorf("Expected generation 2, got %d", blob.Generation)
	}

	// Try to update non-existent blob
	err = bucket.UpdateBlob("nonexistent.json", []byte("data"))
	if err == nil {
		t.Error("UpdateBlob should fail for non-existent blob")
	}
}

// TestFakeGCSDataSource tests the fake GCS data source.
func TestFakeGCSDataSource(t *testing.T) {
	content := []byte(`{
		"metadata": {"generated_at": "2024-01-01T00:00:00Z", "data_version": "test-v1.0"},
		"lookups": {"employees": {}, "teams": {}, "orgs": {}},
		"indexes": {
			"membership": {"membership_index": {}, "relationship_index": {}},
			"slack_id_mappings": {"slack_uid_to_uid": {}},
			"github_id_mappings": {"github_id_to_uid": {}}
		}
	}`)

	source := testingsupport.NewFakeGCSDataSource("org-bucket", "data/org.json", content)

	// Test String()
	str := source.String()
	if str != "gs://org-bucket/data/org.json (fake)" {
		t.Errorf("Unexpected String() result: %q", str)
	}

	// Test Load()
	ctx := context.Background()
	reader, err := source.Load(ctx)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	defer reader.Close()

	// Read content
	buf := make([]byte, 1024)
	n, _ := reader.Read(buf)
	loadedContent := buf[:n]

	// Verify it's valid JSON
	var data map[string]interface{}
	if err := json.Unmarshal(loadedContent, &data); err != nil {
		t.Fatalf("Loaded content is not valid JSON: %v", err)
	}

	// Test Close()
	if err := source.Close(); err != nil {
		t.Errorf("Close failed: %v", err)
	}
}

// TestFakeGCSDataSourceUpdateContent tests hot reload simulation.
func TestFakeGCSDataSourceUpdateContent(t *testing.T) {
	initialContent := []byte(`{"version": 1}`)
	source := testingsupport.NewFakeGCSDataSource("bucket", "data.json", initialContent)

	// Get initial generation
	gen1, err := source.GetGeneration()
	if err != nil {
		t.Fatalf("GetGeneration failed: %v", err)
	}
	if gen1 != 1 {
		t.Errorf("Expected initial generation 1, got %d", gen1)
	}

	// Update content
	newContent := []byte(`{"version": 2}`)
	if err := source.UpdateContent(newContent); err != nil {
		t.Fatalf("UpdateContent failed: %v", err)
	}

	// Check generation increased
	gen2, err := source.GetGeneration()
	if err != nil {
		t.Fatalf("GetGeneration failed: %v", err)
	}
	if gen2 != 2 {
		t.Errorf("Expected generation 2 after update, got %d", gen2)
	}

	// Load and verify new content
	ctx := context.Background()
	reader, err := source.Load(ctx)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	defer reader.Close()

	buf := make([]byte, 1024)
	n, _ := reader.Read(buf)
	if string(buf[:n]) != `{"version": 2}` {
		t.Errorf("Expected updated content, got %q", buf[:n])
	}
}

// TestFakeGCSDataSourceWithService tests using fake GCS with the Service.
func TestFakeGCSDataSourceWithService(t *testing.T) {
	// Create test data JSON
	testData := `{
		"metadata": {
			"generated_at": "2024-01-01T00:00:00Z",
			"data_version": "test-v1.0",
			"total_employees": 1,
			"total_orgs": 1,
			"total_teams": 1
		},
		"lookups": {
			"employees": {
				"testuser": {
					"uid": "testuser",
					"full_name": "Test User",
					"email": "testuser@example.com",
					"job_title": "Engineer"
				}
			},
			"teams": {
				"test-team": {
					"uid": "team1",
					"name": "test-team",
					"type": "team",
					"group": {
						"type": {"name": "team"},
						"resolved_people_uid_list": ["testuser"]
					}
				}
			},
			"orgs": {
				"test-org": {
					"uid": "org1",
					"name": "test-org",
					"type": "organization",
					"group": {
						"type": {"name": "organization"},
						"resolved_people_uid_list": ["testuser"]
					}
				}
			}
		},
		"indexes": {
			"membership": {
				"membership_index": {
					"testuser": [{"name": "test-team", "type": "team"}]
				},
				"relationship_index": {}
			},
			"slack_id_mappings": {"slack_uid_to_uid": {"U123": "testuser"}},
			"github_id_mappings": {"github_id_to_uid": {"gh-user": "testuser"}}
		}
	}`

	source := testingsupport.NewFakeGCSDataSource("org-bucket", "data.json", []byte(testData))

	// Create and load service
	service := NewService()
	ctx := context.Background()
	if err := service.LoadFromDataSource(ctx, source); err != nil {
		t.Fatalf("LoadFromDataSource failed: %v", err)
	}

	// Verify data was loaded
	version := service.GetVersion()
	if version.EmployeeCount != 1 {
		t.Errorf("Expected 1 employee, got %d", version.EmployeeCount)
	}

	// Test queries
	emp := service.GetEmployeeByUID("testuser")
	if emp == nil {
		t.Fatal("GetEmployeeByUID returned nil")
	}
	if emp.FullName != "Test User" {
		t.Errorf("Expected 'Test User', got %q", emp.FullName)
	}

	emp = service.GetEmployeeBySlackID("U123")
	if emp == nil {
		t.Fatal("GetEmployeeBySlackID returned nil")
	}
	if emp.UID != "testuser" {
		t.Errorf("Expected UID 'testuser', got %q", emp.UID)
	}

	team := service.GetTeamByName("test-team")
	if team == nil {
		t.Fatal("GetTeamByName returned nil")
	}
	if team.Name != "test-team" {
		t.Errorf("Expected team name 'test-team', got %q", team.Name)
	}
}

// TestFakeGCSDataSourceHotReload tests simulating a hot reload scenario.
func TestFakeGCSDataSourceHotReload(t *testing.T) {
	// Initial data with 1 employee
	initialData := `{
		"metadata": {"generated_at": "2024-01-01T00:00:00Z", "data_version": "v1"},
		"lookups": {
			"employees": {
				"user1": {"uid": "user1", "full_name": "User One", "email": "user1@test.com", "job_title": "Dev"}
			},
			"teams": {}, "orgs": {}
		},
		"indexes": {
			"membership": {"membership_index": {}, "relationship_index": {}},
			"slack_id_mappings": {"slack_uid_to_uid": {}},
			"github_id_mappings": {"github_id_to_uid": {}}
		}
	}`

	source := testingsupport.NewFakeGCSDataSource("bucket", "data.json", []byte(initialData))
	service := NewService()
	ctx := context.Background()

	// Initial load
	if err := service.LoadFromDataSource(ctx, source); err != nil {
		t.Fatalf("Initial load failed: %v", err)
	}
	if service.GetVersion().EmployeeCount != 1 {
		t.Errorf("Expected 1 employee after initial load")
	}

	// Simulate data update with 2 employees
	updatedData := `{
		"metadata": {"generated_at": "2024-01-02T00:00:00Z", "data_version": "v2"},
		"lookups": {
			"employees": {
				"user1": {"uid": "user1", "full_name": "User One", "email": "user1@test.com", "job_title": "Dev"},
				"user2": {"uid": "user2", "full_name": "User Two", "email": "user2@test.com", "job_title": "Dev"}
			},
			"teams": {}, "orgs": {}
		},
		"indexes": {
			"membership": {"membership_index": {}, "relationship_index": {}},
			"slack_id_mappings": {"slack_uid_to_uid": {}},
			"github_id_mappings": {"github_id_to_uid": {}}
		}
	}`

	// Update the fake GCS content
	if err := source.UpdateContent([]byte(updatedData)); err != nil {
		t.Fatalf("UpdateContent failed: %v", err)
	}

	// Reload
	if err := service.LoadFromDataSource(ctx, source); err != nil {
		t.Fatalf("Reload failed: %v", err)
	}

	// Verify updated data
	if service.GetVersion().EmployeeCount != 2 {
		t.Errorf("Expected 2 employees after reload, got %d", service.GetVersion().EmployeeCount)
	}

	user2 := service.GetEmployeeByUID("user2")
	if user2 == nil {
		t.Fatal("New employee 'user2' not found after reload")
	}
	if user2.FullName != "User Two" {
		t.Errorf("Expected 'User Two', got %q", user2.FullName)
	}
}
