//go:build !gcs

package main

import (
	"context"
	"log"
	"os"
	"time"

	"github.com/go-logr/stdr"
	orgdatacore "github.com/openshift-eng/cyborg-data"
)

func main() {
	// Set up structured logging for the demo
	logger := stdr.New(log.New(os.Stdout, "[GCS-STUB] ", 0))
	orgdatacore.SetLogger(logger)

	logger.Info("=== GCS Example (Stub Mode) ===")
	logger.Info("⚠ WARNING: Built without '-tags gcs'")
	logger.Info("This example demonstrates the GCS API but uses a stub implementation")
	logger.Info("For full GCS functionality, rebuild with: go build -tags gcs .")

	// Create a new service
	service := orgdatacore.NewService()

	// Configure GCS data source
	gcsConfig := orgdatacore.GCSConfig{
		Bucket:        getEnvOrDefault("GCS_BUCKET", "resolved-org"),
		ObjectPath:    getEnvOrDefault("GCS_OBJECT_PATH", "orgdata/comprehensive_index_dump.json"),
		ProjectID:     getEnvOrDefault("GCS_PROJECT_ID", "openshift-crt"),
		CheckInterval: 5 * time.Minute,
	}

	logger.Info("GCS Configuration",
		"bucket", gcsConfig.Bucket+" (stub mode)",
		"object", gcsConfig.ObjectPath+" (stub mode)")

	ctx := context.Background()

	// Create GCS data source (stub version)
	logger.Info("Creating GCS data source", "bucket", gcsConfig.Bucket)
	dataSource := orgdatacore.NewGCSDataSource(gcsConfig)

	// Load data from GCS (will fail with stub)
	if err := service.LoadFromDataSource(ctx, dataSource); err != nil {
		logger.Error(err, "Expected stub error")
		logger.Info("This is expected behavior in stub mode")
		logger.Info("To use real GCS functionality",
			"step1", "go get cloud.google.com/go/storage",
			"step2", "go build -tags gcs .",
			"step3", "Set up GCS authentication",
			"step4", "./with-gcs")
		return
	}

	// This won't be reached in stub mode, but shows the API
	logger.Info("Successfully loaded data", "source", dataSource.String())
	logger.Info("Note: This demonstrates the identical API regardless of implementation!")
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
