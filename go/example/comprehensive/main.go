package main

import (
	"context"
	"log/slog"
	"os"
	"time"

	orgdatacore "github.com/openshift-eng/cyborg-data/go"
)

func main() {
	// Set up structured logging for the demo
	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	orgdatacore.SetLogger(logger)

	logger.Info("=== Organizational Data Core Package Demo ===")

	// Show version info
	versionInfo := orgdatacore.GetVersionInfo()
	logger.Info("Library version", "version", versionInfo.Version, "commit", versionInfo.GitCommit)

	// Create a new service with options
	service := orgdatacore.NewService(
		orgdatacore.WithLogger(logger),
	)

	// Example 1: GCS DataSource (production data source)
	if hasGCSConfig() {
		logger.Info("--- GCS DataSource Example ---")
		demonstrateGCSDataSource(service, logger)
	} else {
		logger.Info("--- GCS DataSource Example (Configuration Required) ---")
		demonstrateGCSDataSourceStub(logger)
	}

	// Example 2: Advanced queries (only if data was loaded)
	version := service.GetVersion()
	if version.EmployeeCount > 0 {
		logger.Info("--- Advanced Queries Example ---")
		demonstrateAdvancedQueries(service, logger)
	}

	logger.Info("Core package is ready for use!",
		"import", "github.com/openshift-eng/cyborg-data/go",
		"interface", "orgdatacore.ServiceInterface",
		"implementation", "orgdatacore.Service",
		"datasources", "GCS (with -tags gcs build flag)")
}

func demonstrateService(service *orgdatacore.Service, logger *slog.Logger) {
	// Get version info
	version := service.GetVersion()
	logger.Info("Data loaded",
		"loadTime", version.LoadTime.Format(time.RFC3339),
		"employeeCount", version.EmployeeCount,
		"orgCount", version.OrgCount)

	// Example employee lookup
	if employee := service.GetEmployeeByUID("jsmith"); employee != nil {
		logger.Info("Found employee", "name", employee.FullName, "uid", employee.UID)
	}

	// Example team membership check
	teams := service.GetTeamsForUID("jsmith")
	if len(teams) > 0 {
		logger.Info("User team membership", "uid", "jsmith", "teams", teams)
	}
}

func demonstrateAdvancedQueries(service *orgdatacore.Service, logger *slog.Logger) {
	// Employee lookups by different IDs
	if employee := service.GetEmployeeBySlackID("U12345678"); employee != nil {
		logger.Info("Slack ID mapping", "slackID", "U12345678", "uid", employee.UID, "name", employee.FullName)
	}

	if employee := service.GetEmployeeByGitHubID("jsmith-dev"); employee != nil {
		logger.Info("GitHub ID mapping", "githubID", "jsmith-dev", "uid", employee.UID, "name", employee.FullName)
		// Show new employee fields
		if employee.RhatGeo != "" || employee.CostCenter != 0 {
			logger.Info("Employee details",
				"rhatGeo", employee.RhatGeo,
				"costCenter", employee.CostCenter,
				"managerUID", employee.ManagerUID,
				"isPeopleManager", employee.IsPeopleManager)
		}
	}

	// Email lookup (case-insensitive)
	if employee := service.GetEmployeeByEmail("jsmith@example.com"); employee != nil {
		logger.Info("Email lookup", "email", "jsmith@example.com", "uid", employee.UID, "name", employee.FullName)
	}

	// Team membership checks
	isInTeam := service.IsEmployeeInTeam("jsmith", "test-team")
	logger.Info("Employee team membership", "uid", "jsmith", "team", "test-team", "isMember", isInTeam)

	// Slack user team membership
	isSlackInTeam := service.IsSlackUserInTeam("U12345678", "test-team")
	logger.Info("Slack user team membership", "slackID", "U12345678", "team", "test-team", "isMember", isSlackInTeam)

	// Get team members
	teamMembers := service.GetTeamMembers("test-team")
	logger.Info("Team member count", "team", "test-team", "memberCount", len(teamMembers))

	// Organization, Pillar, and TeamGroup queries
	if org := service.GetOrgByName("test-org"); org != nil {
		logger.Info("Organization lookup", "name", org.Name, "type", org.Type)
	}

	if pillar := service.GetPillarByName("engineering"); pillar != nil {
		logger.Info("Pillar lookup", "name", pillar.Name, "type", pillar.Type)
	}

	if teamGroup := service.GetTeamGroupByName("backend-teams"); teamGroup != nil {
		logger.Info("Team group lookup", "name", teamGroup.Name, "type", teamGroup.Type)
	}

	// Organization membership
	userOrgs := service.GetUserOrganizations("U12345678")
	if len(userOrgs) > 0 {
		logger.Info("User organizations", "slackID", "U12345678", "orgCount", len(userOrgs))
	}

	// Enumeration methods (slice-based)
	allTeams := service.GetAllTeamNames()
	allOrgs := service.GetAllOrgNames()
	allPillars := service.GetAllPillarNames()
	allTeamGroups := service.GetAllTeamGroupNames()
	logger.Info("Data statistics",
		"totalTeams", len(allTeams),
		"totalOrgs", len(allOrgs),
		"totalPillars", len(allPillars),
		"totalTeamGroups", len(allTeamGroups))

	// Iterator-based enumeration (Go 1.23+)
	// These use a snapshot approach - safe for concurrent use
	logger.Info("--- Iterator Examples (Go 1.23+) ---")

	// Count employees using iterator
	employeeCount := 0
	for range service.AllEmployeeUIDs() {
		employeeCount++
	}
	logger.Info("Counted employees via iterator", "count", employeeCount)

	// Find first manager using iterator
	for emp := range service.AllEmployees() {
		if emp.IsPeopleManager {
			logger.Info("Found first manager via iterator", "uid", emp.UID, "name", emp.FullName)
			break
		}
	}

	// Iterate over teams with key-value pairs
	teamCount := 0
	for name, team := range service.AllTeams() {
		if teamCount == 0 {
			logger.Info("First team from iterator", "name", name, "type", team.Type)
		}
		teamCount++
	}
	logger.Info("Counted teams via iterator", "count", teamCount)
}

func hasGCSConfig() bool {
	return os.Getenv("GCS_BUCKET") != "" &&
		(os.Getenv("GOOGLE_APPLICATION_CREDENTIALS") != "" || os.Getenv("GCS_CREDENTIALS_JSON") != "")
}

func demonstrateGCSDataSource(service *orgdatacore.Service, logger *slog.Logger) {
	config := orgdatacore.GCSConfig{
		Bucket:          getEnvDefault("GCS_BUCKET", "resolved-org"),
		ObjectPath:      getEnvDefault("GCS_OBJECT_PATH", "orgdata/comprehensive_index_dump.json"),
		ProjectID:       getEnvDefault("GCS_PROJECT_ID", "openshift-crt"),
		CredentialsJSON: os.Getenv("GCS_CREDENTIALS_JSON"),
		CheckInterval:   5 * time.Minute,
	}

	logger.Info("Attempting to load from GCS", "bucket", config.Bucket, "object", config.ObjectPath)

	// Note: This will fail unless built with -tags gcs
	gcsSource := orgdatacore.NewGCSDataSource(config)
	defer gcsSource.Close()

	err := service.LoadFromDataSource(context.Background(), gcsSource)
	if err != nil {
		logger.Error("GCS load failed (expected without -tags gcs)", "error", err)
		logger.Info("To enable GCS support",
			"step1", "go get cloud.google.com/go/storage",
			"step2", "go build -tags gcs",
			"step3", "Use NewGCSDataSourceWithSDK() instead")
	} else {
		logger.Info("Loaded organizational data from GCS", "source", gcsSource.String())
		demonstrateService(service, logger)

		// Start watching for changes
		logger.Info("Setting up GCS change watcher...")
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		err = service.StartDataSourceWatcher(ctx, gcsSource)
		if err != nil {
			logger.Error("GCS watcher failed", "error", err)
		} else {
			logger.Info("Started GCS watcher (will check for updates every 5 minutes)")
		}
	}
}

func demonstrateGCSDataSourceStub(logger *slog.Logger) {
	logger.Info("GCS DataSource is the production data source")

	logger.Info("GCS DataSource Configuration Example")
	logger.Info("Environment variables needed",
		"GCS_BUCKET", "resolved-org",
		"GCS_OBJECT_PATH", "orgdata/comprehensive_index_dump.json",
		"GCS_PROJECT_ID", "openshift-crt",
		"GOOGLE_APPLICATION_CREDENTIALS", "/path/to/service-account.json")
	logger.Info("Alternative authentication", "GCS_CREDENTIALS_JSON", `{"type":"service_account",...}`)

	logger.Info("To enable full GCS support",
		"step1", "Build with GCS tag: go build -tags gcs",
		"step2", "Use NewGCSDataSourceWithSDK() to create the data source",
		"step3", "Set appropriate environment variables for authentication")

	// Show how it would work
	config := orgdatacore.GCSConfig{
		Bucket:        "resolved-org",
		ObjectPath:    "orgdata/comprehensive_index_dump.json",
		ProjectID:     "openshift-crt",
		CheckInterval: 5 * time.Minute,
	}

	source := orgdatacore.NewGCSDataSource(config)
	defer source.Close()

	logger.Info("GCS DataSource stub created", "source", source.String())
	logger.Info("Note: This stub will error until built with -tags gcs")
}

func getEnvDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
