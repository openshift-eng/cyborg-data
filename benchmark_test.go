package orgdatacore

import (
	"context"
	"path/filepath"
	"testing"
)

// setupBenchmarkService creates a service for benchmarking
func setupBenchmarkService(b *testing.B) *Service {
	b.Helper()
	service := NewService()

	testDataPath := filepath.Join("testdata", "test_org_data.json")
	fileSource := NewFileDataSource(testDataPath)

	if err := service.LoadFromDataSource(context.Background(), fileSource); err != nil {
		b.Fatalf("Failed to load test data: %v", err)
	}

	return service
}

// BenchmarkGetEmployeeByUID benchmarks employee lookup by UID
func BenchmarkGetEmployeeByUID(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.GetEmployeeByUID("jsmith")
	}
}

// BenchmarkGetEmployeeBySlackID benchmarks employee lookup by Slack ID
func BenchmarkGetEmployeeBySlackID(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.GetEmployeeBySlackID("U12345678")
	}
}

// BenchmarkGetEmployeeBySlackID benchmarks employee lookup by Slack ID
func BenchmarkGetEmployeeByGitHubID(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.GetEmployeeByGitHubID("ghuser1")
	}
}

// BenchmarkGetTeamByName benchmarks team lookup
func BenchmarkGetTeamByName(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.GetTeamByName("test-team")
	}
}

// BenchmarkIsEmployeeInTeam benchmarks team membership checks
func BenchmarkIsEmployeeInTeam(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.IsEmployeeInTeam("jsmith", "test-team")
	}
}

// BenchmarkIsEmployeeInOrg benchmarks organization membership checks
func BenchmarkIsEmployeeInOrg(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.IsEmployeeInOrg("jsmith", "test-org")
	}
}

// BenchmarkGetTeamsForUID benchmarks team list retrieval
func BenchmarkGetTeamsForUID(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.GetTeamsForUID("jsmith")
	}
}

// BenchmarkGetUserOrganizations benchmarks complete org hierarchy retrieval
func BenchmarkGetUserOrganizations(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		service.GetUserOrganizations("U98765432")
	}
}

// BenchmarkConcurrentReads benchmarks concurrent read performance
func BenchmarkConcurrentReads(b *testing.B) {
	service := setupBenchmarkService(b)

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			// Mix of different queries
			switch b.N % 4 {
			case 0:
				service.GetEmployeeByUID("jsmith")
			case 1:
				service.GetTeamByName("test-team")
			case 2:
				service.IsEmployeeInTeam("jsmith", "test-team")
			case 3:
				service.GetTeamsForUID("adoe")
			}
		}
	})
}
