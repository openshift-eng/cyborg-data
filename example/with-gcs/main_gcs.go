//go:build gcs
// +build gcs

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
	log.SetFlags(0)
	fmt.Println("=== GCS Example (With Cloud Dependencies) ===")
	fmt.Println("This example demonstrates using cyborg-data with Google Cloud Storage.")
	fmt.Println("Built with '-tags gcs' - using real GCS implementation")
	fmt.Println()

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

	fmt.Printf("Using bucket: %s\n", gcsConfig.Bucket)
	fmt.Printf("Using object: %s\n", gcsConfig.ObjectPath)
	fmt.Println("✓ Real GCS implementation enabled")
	fmt.Println()

	ctx := context.Background()

	// Create GCS data source with full SDK support
	fmt.Printf("Creating GCS data source: gs://%s/%s\n", gcsConfig.Bucket, gcsConfig.ObjectPath)

	gcsSource, err := orgdatacore.NewGCSDataSourceWithSDK(ctx, gcsConfig)
	if err != nil {
		log.Fatalf("Failed to create GCS data source: %v", err)
	}

	// Load data from GCS
	if err := service.LoadFromDataSource(ctx, gcsSource); err != nil {
		log.Printf("Failed to load from GCS: %v", err)
		fmt.Println()
		fmt.Println("This is expected if:")
		fmt.Println("  - You don't have access to the resolved-org bucket")
		fmt.Println("  - Authentication is not configured")
		fmt.Println()
		return
	}

	fmt.Printf("Successfully loaded data from: %s\n", gcsSource.String())

	// Demonstrate queries
	demonstrateQueries(service)

	// Start GCS watcher for hot reload
	fmt.Println("\n--- GCS Watching Demo ---")
	fmt.Println("Starting GCS watcher (checks for updates every 5 minutes)...")

	go func() {
		if err := service.StartDataSourceWatcher(ctx, gcsSource); err != nil {
			log.Printf("GCS watcher error: %v", err)
		}
	}()

	fmt.Println("GCS watcher started successfully")
	fmt.Println("   - Polls GCS object metadata every 5 minutes")
	fmt.Println("   - Automatically reloads when object is updated")
	fmt.Println("   - Uses structured logging for observability")

	// Keep program running to demonstrate watcher (in real usage)
	fmt.Println("\n--- Watching for changes (demo: 10 seconds) ---")
	time.Sleep(10 * time.Second)
	fmt.Println("Demo complete!")
}

func demonstrateQueries(service *orgdatacore.Service) {
	fmt.Println("\n--- Query Examples ---")

	// Get version info
	version := service.GetVersion()
	fmt.Printf("Data version: %d employees, %d orgs (loaded at %s)\n",
		version.EmployeeCount, version.OrgCount, version.LoadTime.Format("15:04:05"))

	// Show that queries are identical regardless of data source
	fmt.Println("Note: All queries work identically whether data comes from files or GCS!")

	// Example queries (same as file-only example)
	if emp := service.GetEmployeeByUID("jsmith"); emp != nil {
		fmt.Printf("Employee: %s (%s) - %s\n", emp.FullName, emp.UID, emp.JobTitle)
	}

	teams := service.GetTeamsForUID("jsmith")
	if len(teams) > 0 {
		fmt.Printf("Teams for jsmith: %v\n", teams)
	}
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
