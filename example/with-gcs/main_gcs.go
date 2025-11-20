//go:build gcs
// +build gcs

package main

import (
	"context"
	"log"
	"os"
	"time"

	"github.com/go-logr/logr"
	"github.com/go-logr/stdr"
	orgdatacore "github.com/openshift-eng/cyborg-data"
)

func main() {
	// Set up structured logging for the demo
	logger := stdr.New(log.New(os.Stdout, "[GCS-REAL] ", 0))
	orgdatacore.SetLogger(logger)

	logger.Info("=== GCS Example (With Cloud Dependencies) ===")
	logger.Info("This example demonstrates using cyborg-data with Google Cloud Storage")
	logger.Info("Built with '-tags gcs' - using real GCS implementation")

	// Create a new service
	service := orgdatacore.NewService()

	// Configure GCS data source
	gcsConfig := orgdatacore.GCSConfig{
		Bucket:        getEnvOrDefault("GCS_BUCKET", "resolved-org"),
		ObjectPath:    getEnvOrDefault("GCS_OBJECT_PATH", "orgdata/comprehensive_index_dump.json"),
		ProjectID:     getEnvOrDefault("GCS_PROJECT_ID", "openshift-crt"),
		CheckInterval: 5 * time.Minute,
		// Optional: Use service account credentials
		// CredentialsJSON: os.Getenv("GCS_CREDENTIALS_JSON"),
	}

	logger.Info("GCS Configuration",
		"bucket", gcsConfig.Bucket,
		"object", gcsConfig.ObjectPath,
		"status", "Real GCS implementation enabled")

	ctx := context.Background()

	// Create GCS data source with full SDK support
	logger.Info("Creating GCS data source", "uri", "gs://"+gcsConfig.Bucket+"/"+gcsConfig.ObjectPath)

	gcsSource, err := orgdatacore.NewGCSDataSourceWithSDK(ctx, gcsConfig)
	if err != nil {
		logger.Error(err, "Failed to create GCS data source")
		os.Exit(1)
	}

	// Load data from GCS
	if err := service.LoadFromDataSource(ctx, gcsSource); err != nil {
		logger.Error(err, "Failed to load from GCS")
		logger.Info("This is expected if",
			"reason1", "You don't have access to the resolved-org bucket",
			"reason2", "Authentication is not configured")
		return
	}

	logger.Info("Successfully loaded data", "source", gcsSource.String())

	// Demonstrate queries
	demonstrateQueries(service, logger)

	// Start GCS watcher for hot reload
	logger.Info("--- GCS Watching Demo ---")
	logger.Info("Starting GCS watcher (checks for updates every 5 minutes)")

	go func() {
		if err := service.StartDataSourceWatcher(ctx, gcsSource); err != nil {
			logger.Error(err, "GCS watcher error")
		}
	}()

	logger.Info("GCS watcher started successfully",
		"pollInterval", "5 minutes",
		"feature", "Automatically reloads when object is updated",
		"logging", "Uses structured logging for observability")

	// Keep program running to demonstrate watcher (in real usage)
	logger.Info("--- Watching for changes (demo: 10 seconds) ---")
	time.Sleep(10 * time.Second)
	logger.Info("Demo complete!")
}

func demonstrateQueries(service *orgdatacore.Service, logger logr.Logger) {
	logger.Info("--- Query Examples ---")

	// Get version info
	version := service.GetVersion()
	logger.Info("Data version",
		"employeeCount", version.EmployeeCount,
		"orgCount", version.OrgCount,
		"loadTime", version.LoadTime.Format("15:04:05"))

	// Show that queries are identical regardless of data source
	logger.Info("Note: All queries work identically with any data source!")

	// Employee lookups by different IDs
	if emp := service.GetEmployeeByUID("jsmith"); emp != nil {
		logger.Info("Employee lookup by UID", "name", emp.FullName, "uid", emp.UID, "jobTitle", emp.JobTitle)
	}

	if emp := service.GetEmployeeBySlackID("U12345678"); emp != nil {
		logger.Info("Employee lookup by Slack ID", "slackID", "U12345678", "uid", emp.UID)
	}

	if emp := service.GetEmployeeByGitHubID("jsmith-dev"); emp != nil {
		logger.Info("Employee lookup by GitHub ID", "githubID", "jsmith-dev", "uid", emp.UID)
	}

	// Team membership
	teams := service.GetTeamsForUID("jsmith")
	if len(teams) > 0 {
		logger.Info("Team membership", "uid", "jsmith", "teams", teams)
	}

	// Organization, pillar, and team group queries
	if org := service.GetOrgByName("test-org"); org != nil {
		logger.Info("Organization query", "name", org.Name)
	}

	if pillar := service.GetPillarByName("engineering"); pillar != nil {
		logger.Info("Pillar query", "name", pillar.Name)
	}

	if teamGroup := service.GetTeamGroupByName("backend-teams"); teamGroup != nil {
		logger.Info("Team group query", "name", teamGroup.Name)
	}
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
