//go:build !gcs
// +build !gcs

package main

import (
	"context"
	"fmt"
	"os"
	"time"

	orgdatacore "github.com/openshift-eng/cyborg-data"
)

func main() {
	fmt.Println("=== GCS Example (Stub Mode) ===")
	fmt.Println("⚠ WARNING: Built without '-tags gcs'")
	fmt.Println("This example demonstrates the GCS API but uses a stub implementation.")
	fmt.Println("For full GCS functionality, rebuild with: go build -tags gcs .")
	fmt.Println()

	// Create a new service
	service := orgdatacore.NewService()

	// Configure GCS data source
	gcsConfig := orgdatacore.GCSConfig{
		Bucket:        getEnvOrDefault("GCS_BUCKET", "resolved-org"),
		ObjectPath:    getEnvOrDefault("GCS_OBJECT_PATH", "orgdata/comprehensive_index_dump.json"),
		ProjectID:     getEnvOrDefault("GCS_PROJECT_ID", "openshift-crt"),
		CheckInterval: 5 * time.Minute,
	}

	fmt.Printf("Using bucket: %s (stub mode)\n", gcsConfig.Bucket)
	fmt.Printf("Using object: %s (stub mode)\n", gcsConfig.ObjectPath)
	fmt.Println()

	ctx := context.Background()

	// Create GCS data source (stub version)
	fmt.Printf("Creating GCS data source: %s\n", gcsConfig.Bucket)
	dataSource := orgdatacore.NewGCSDataSource(gcsConfig)

	// Load data from GCS (will fail with stub)
	if err := service.LoadFromDataSource(ctx, dataSource); err != nil {
		fmt.Printf("Expected stub error: %v\n", err)
		fmt.Println()
		fmt.Println("This is expected behavior in stub mode.")
		fmt.Println("To use real GCS functionality:")
		fmt.Println("  1. go get cloud.google.com/go/storage")
		fmt.Println("  2. go build -tags gcs .")
		fmt.Println("  3. Set up GCS authentication")
		fmt.Println("  4. ./with-gcs")
		return
	}

	// This won't be reached in stub mode, but shows the API
	fmt.Printf("Successfully loaded data from: %s\n", dataSource.String())
	fmt.Println("Note: This demonstrates the identical API regardless of implementation!")
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
