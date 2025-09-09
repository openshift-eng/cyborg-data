package main

import (
	"context"
	"fmt"
	"log"

	orgdatacore "github.com/openshift-eng/cyborg-data"
)

func main() {
	fmt.Println("=== File-Only Example (No GCS Dependencies) ===")
	fmt.Println("This example demonstrates using cyborg-data with local files only.")
	fmt.Println("No cloud dependencies are required - lightweight and simple!")
	fmt.Println()

	// Create a new service
	service := orgdatacore.NewService()

	// Use file-based data source - no external dependencies needed
	fileSource := orgdatacore.NewFileDataSource("../../testdata/test_org_data.json")

	ctx := context.Background()

	// Load data from file
	if err := service.LoadFromDataSource(ctx, fileSource); err != nil {
		log.Fatalf("Failed to load organizational data: %v", err)
	}

	fmt.Printf("Successfully loaded data from: %s\n", fileSource.String())

	// Demonstrate queries
	demonstrateQueries(service)

	// Start file watcher for hot reload (optional)
	fmt.Println("\n--- File Watching Demo ---")
	fmt.Println("Starting file watcher (would detect changes automatically)...")

	// In a real application, you'd run this in a goroutine and keep the program running
	// go func() {
	// 	if err := service.StartDataSourceWatcher(ctx, fileSource); err != nil {
	// 		log.Printf("File watcher error: %v", err)
	// 	}
	// }()

	fmt.Println("File watcher setup complete (demo mode - not actually watching)")

	fmt.Println("\n=== Build Instructions ===")
	fmt.Println("go build example-file-only.go")
	fmt.Println("# No special build tags or dependencies required!")
}

func demonstrateQueries(service *orgdatacore.Service) {
	fmt.Println("\n--- Query Examples ---")

	// Get version info
	version := service.GetVersion()
	fmt.Printf("Data version: %d employees, %d orgs (loaded at %s)\n",
		version.EmployeeCount, version.OrgCount, version.LoadTime.Format("15:04:05"))

	// Employee lookups
	if emp := service.GetEmployeeByUID("jsmith"); emp != nil {
		fmt.Printf("Employee: %s (%s) - %s\n", emp.FullName, emp.UID, emp.JobTitle)
	}

	// Team membership
	teams := service.GetTeamsForUID("jsmith")
	if len(teams) > 0 {
		fmt.Printf("Teams for jsmith: %v\n", teams)
	}

	// Organization queries
	orgs := service.GetUserOrganizations("U12345678")
	if len(orgs) > 0 {
		fmt.Printf("Organizations for Slack user: %d total\n", len(orgs))
	}
}
