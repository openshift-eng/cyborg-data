package main

import (
	"context"
	"log"
	"os"

	"github.com/go-logr/logr"
	"github.com/go-logr/stdr"
	orgdatacore "github.com/openshift-eng/cyborg-data"
)

func main() {
	// Set up structured logging for the demo
	logger := stdr.New(log.New(os.Stdout, "[FILE-DEMO] ", 0))
	orgdatacore.SetLogger(logger)

	logger.Info("=== File-Only Example (No GCS Dependencies) ===")
	logger.Info("This example demonstrates using cyborg-data with local files only")
	logger.Info("No cloud dependencies are required - lightweight and simple!")

	// Create a new service
	service := orgdatacore.NewService()

	// Use file-based data source - no external dependencies needed
	fileSource := orgdatacore.NewFileDataSource("../../testdata/test_org_data.json")

	ctx := context.Background()

	// Load data from file
	if err := service.LoadFromDataSource(ctx, fileSource); err != nil {
		logger.Error(err, "Failed to load organizational data")
		os.Exit(1)
	}

	logger.Info("Successfully loaded data", "source", fileSource.String())

	// Demonstrate queries
	demonstrateQueries(service, logger)

	// Start file watcher for hot reload (optional)
	logger.Info("--- File Watching Demo ---")
	logger.Info("Starting file watcher (would detect changes automatically)")

	// In a real application, you'd run this in a goroutine and keep the program running
	// go func() {
	// 	if err := service.StartDataSourceWatcher(ctx, fileSource); err != nil {
	// 		logger.Error(err, "File watcher error")
	// 	}
	// }()

	logger.Info("File watcher setup complete (demo mode - not actually watching)")

	logger.Info("=== Build Instructions ===",
		"command", "go build example-file-only.go",
		"note", "No special build tags or dependencies required!")
}

func demonstrateQueries(service *orgdatacore.Service, logger logr.Logger) {
	logger.Info("--- Query Examples ---")

	// Get version info
	version := service.GetVersion()
	logger.Info("Data version",
		"employeeCount", version.EmployeeCount,
		"orgCount", version.OrgCount,
		"loadTime", version.LoadTime.Format("15:04:05"))

	// Employee lookups
	if emp := service.GetEmployeeByUID("jsmith"); emp != nil {
		logger.Info("Employee lookup", "name", emp.FullName, "uid", emp.UID, "jobTitle", emp.JobTitle)
	}

	// Team membership
	teams := service.GetTeamsForUID("jsmith")
	if len(teams) > 0 {
		logger.Info("Team membership", "uid", "jsmith", "teams", teams)
	}

	// Organization queries
	orgs := service.GetUserOrganizations("U12345678")
	if len(orgs) > 0 {
		logger.Info("Organization membership", "slackID", "U12345678", "orgCount", len(orgs))
	}
}
