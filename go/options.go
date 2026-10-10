package orgdatacore

import (
	"log/slog"
	"time"
)

// ServiceOption configures a Service instance.
type ServiceOption func(*serviceConfig)

type serviceConfig struct {
	logger           *slog.Logger
	historyCacheSize int
	versionsCacheTTL time.Duration
}

// defaultHistoryCacheSize is the number of historical snapshots AsOf keeps
// cached in memory per Service. Each snapshot is a full org dataset, so this is
// deliberately small.
const defaultHistoryCacheSize = 4

// defaultVersionsCacheTTL is how long AsOf/ListVersions reuse a cached version
// listing before re-querying the source. Keeps repeated historical queries from
// re-listing the bucket on every call.
const defaultVersionsCacheTTL = 60 * time.Second

func defaultServiceConfig() *serviceConfig {
	return &serviceConfig{
		logger:           slog.Default(),
		historyCacheSize: defaultHistoryCacheSize,
		versionsCacheTTL: defaultVersionsCacheTTL,
	}
}

// WithLogger sets a custom logger for the service.
func WithLogger(logger *slog.Logger) ServiceOption {
	return func(c *serviceConfig) {
		if logger != nil {
			c.logger = logger
		}
	}
}

// WithHistoryCacheSize sets how many historical snapshots AsOf keeps cached in
// memory (LRU). A size <= 0 disables caching (every AsOf re-downloads). Defaults
// to defaultHistoryCacheSize.
func WithHistoryCacheSize(size int) ServiceOption {
	return func(c *serviceConfig) {
		c.historyCacheSize = size
	}
}

// WithVersionsCacheTTL sets how long AsOf/ListVersions reuse a cached version
// listing before re-querying the source. A TTL <= 0 disables it (every call
// re-lists). Defaults to defaultVersionsCacheTTL.
func WithVersionsCacheTTL(ttl time.Duration) ServiceOption {
	return func(c *serviceConfig) {
		c.versionsCacheTTL = ttl
	}
}
