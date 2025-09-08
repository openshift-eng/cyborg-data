package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	orgdatacore "github.com/openshift-eng/cyborg-data"
)

func main() {
	fmt.Println("=== Organizational Data Core Package Demo ===")
	fmt.Println()

	// Create a new service
	service := orgdatacore.NewService()

	// Example 1: Load data using DataSource interface (recommended approach)
	fmt.Println("--- DataSource Interface Example ---")
	fileSource := orgdatacore.NewFileDataSource("../../testdata/test_org_data.json")

	err := service.LoadFromDataSource(context.Background(), fileSource)
	if err != nil {
		log.Printf("    Could not load via DataSource: %v", err)
	} else {
		fmt.Printf("Loaded organizational data via DataSource: %s\n", fileSource.String())
		demonstrateService(service)
	}

	// Example 2: File watching with hot reload
	fmt.Println("\n--- File Watching Example ---")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err = service.StartDataSourceWatcher(ctx, fileSource)
	if err != nil {
		log.Printf("    File watcher setup: %v", err)
	} else {
		fmt.Println("File watcher started successfully (would monitor for changes)")
	}

	// Example 3: Advanced queries with Jira integration
	fmt.Println("\n--- Advanced Queries Example ---")
	demonstrateAdvancedQueries(service)

	// Example 4: GCS DataSource (if you have GCS credentials)
	if hasGCSConfig() {
		fmt.Println("\n--- GCS DataSource Example ---")
		demonstrateGCSDataSource(service)
	} else {
		fmt.Println("\n--- GCS DataSource Example (Simulated) ---")
		demonstrateGCSDataSourceStub()
	}

	fmt.Println("\nCore package is ready for use!")
	fmt.Println("   - Import: github.com/openshift-eng/cyborg-data")
	fmt.Println("   - Interface: orgdatacore.ServiceInterface")
	fmt.Println("   - Implementation: orgdatacore.Service")
	fmt.Println("   - Data Sources: File, GCS (with build tag), HTTP (future)")
}

func demonstrateService(service *orgdatacore.Service) {
	// Get version info
	version := service.GetVersion()
	fmt.Printf("Data loaded at: %s\n", version.LoadTime.Format(time.RFC3339))
	fmt.Printf("Employee count: %d, Org count: %d\n", version.EmployeeCount, version.OrgCount)

	// Example employee lookup
	if employee := service.GetEmployeeByUID("jsmith"); employee != nil {
		fmt.Printf("Found employee: %s (%s)\n", employee.FullName, employee.UID)
	}

	// Example team membership check
	teams := service.GetTeamsForUID("jsmith")
	if len(teams) > 0 {
		fmt.Printf("User is member of teams: %v\n", teams)
	}
}

func demonstrateAdvancedQueries(service *orgdatacore.Service) {
	// Slack ID to UID mapping
	if employee := service.GetEmployeeBySlackID("U12345678"); employee != nil {
		fmt.Printf("Slack ID U12345678 maps to employee: %s\n", employee.UID)
	}

	// Team membership checks
	isInTeam := service.IsEmployeeInTeam("jsmith", "test-team")
	fmt.Printf("Employee jsmith in test-team: %t\n", isInTeam)

	// Slack user team membership
	isSlackInTeam := service.IsSlackUserInTeam("U12345678", "test-team")
	fmt.Printf("Slack user U12345678 in test-team: %t\n", isSlackInTeam)

	// Get team members
	teamMembers := service.GetTeamMembers("test-team")
	fmt.Printf("test-team has %d members\n", len(teamMembers))

	// Organization membership
	userOrgs := service.GetUserOrganizations("U12345678")
	if len(userOrgs) > 0 {
		fmt.Printf("User organizations: %v\n", userOrgs)
	}
}

func hasGCSConfig() bool {
	return os.Getenv("GCS_BUCKET") != "" &&
		(os.Getenv("GOOGLE_APPLICATION_CREDENTIALS") != "" || os.Getenv("GCS_CREDENTIALS_JSON") != "")
}

func demonstrateGCSDataSource(service *orgdatacore.Service) {
	config := orgdatacore.GCSConfig{
		Bucket:          getEnvDefault("GCS_BUCKET", "resolved-org"),
		ObjectPath:      getEnvDefault("GCS_OBJECT_PATH", "orgdata/comprehensive_index_dump.json"),
		ProjectID:       getEnvDefault("GCS_PROJECT_ID", "openshift-crt-mce"),
		CredentialsJSON: os.Getenv("GCS_CREDENTIALS_JSON"),
		CheckInterval:   5 * time.Minute,
	}

	fmt.Printf("Attempting to load from GCS: %s/%s\n", config.Bucket, config.ObjectPath)

	// Note: This will fail unless built with -tags gcs
	gcsSource := orgdatacore.NewGCSDataSource(config)

	err := service.LoadFromDataSource(context.Background(), gcsSource)
	if err != nil {
		log.Printf("    GCS load failed (expected without -tags gcs): %v", err)
		fmt.Println("    To enable GCS support:")
		fmt.Println("      1. go get cloud.google.com/go/storage")
		fmt.Println("      2. go build -tags gcs")
		fmt.Println("      3. Use NewGCSDataSourceWithSDK() instead")
	} else {
		fmt.Printf("Loaded organizational data from GCS: %s\n", gcsSource.String())
		demonstrateService(service)

		// Start watching for changes
		fmt.Println("Setting up GCS change watcher...")
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		err = service.StartDataSourceWatcher(ctx, gcsSource)
		if err != nil {
			log.Printf("    GCS watcher failed: %v", err)
		} else {
			fmt.Println("Started GCS watcher (will check for updates every 5 minutes)")
		}
	}
}

func demonstrateGCSDataSourceStub() {
	fmt.Println("GCS DataSource Configuration Example:")
	fmt.Println("   export GCS_BUCKET=resolved-org")
	fmt.Println("   export GCS_OBJECT_PATH=orgdata/comprehensive_index_dump.json")
	fmt.Println("   export GCS_PROJECT_ID=openshift-crt-mce")
	fmt.Println("   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json")
	fmt.Println("   # OR")
	fmt.Println("   export GCS_CREDENTIALS_JSON='{\"type\":\"service_account\",...}'")
	fmt.Println()
	fmt.Println("To enable full GCS support:")
	fmt.Println("   go get cloud.google.com/go/storage")
	fmt.Println("   go build -tags gcs")
	fmt.Println()

	// Show how it would work
	config := orgdatacore.GCSConfig{
		Bucket:        "resolved-org",
		ObjectPath:    "orgdata/comprehensive_index_dump.json",
		ProjectID:     "openshift-crt-mce",
		CheckInterval: 5 * time.Minute,
	}

	source := orgdatacore.NewGCSDataSource(config)
	fmt.Printf("GCS DataSource created: %s\n", source.String())
}

func getEnvDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
