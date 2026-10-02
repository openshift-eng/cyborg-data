package orgdatacore

import "log/slog"

// ServiceOption configures a Service instance.
type ServiceOption func(*serviceConfig)

type serviceConfig struct {
	logger           *slog.Logger
	historyCacheSize int
}

// defaultHistoryCacheSize is the number of historical snapshots AsOf keeps
// cached in memory per Service. Each snapshot is a full org dataset, so this is
// deliberately small.
const defaultHistoryCacheSize = 4

func defaultServiceConfig() *serviceConfig {
	return &serviceConfig{logger: slog.Default(), historyCacheSize: defaultHistoryCacheSize}
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
