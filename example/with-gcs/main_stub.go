//go:build !gcs

package main

import (
	"context"
	"log/slog"
	"os"
	"time"

	orgdatacore "github.com/openshift-eng/cyborg-data"
)

func main() {
	// Set up structured logging for the demo
	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	orgdatacore.SetLogger(logger)

	logger.Info("=== GCS Example (Stub Mode) ===")
	logger.Warn("Built without '-tags gcs'")
	logger.Info("This example demonstrates the GCS API but uses a stub implementation")
	logger.Info("For full GCS functionality, rebuild with: go build -tags gcs .")

	// Show version info
	versionInfo := orgdatacore.GetVersionInfo()
	logger.Info("Library version", "version", versionInfo.Version, "commit", versionInfo.GitCommit)

	// Create a new service with options
	service := orgdatacore.NewService(
		orgdatacore.WithLogger(logger),
	)

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
	defer dataSource.Close()

	// Load data from GCS (will fail with stub)
	if err := service.LoadFromDataSource(ctx, dataSource); err != nil {
		logger.Error("Expected stub error", "error", err)
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
