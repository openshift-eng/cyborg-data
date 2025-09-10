all: test examples

# Build all examples
examples: file-only-example gcs-example comprehensive-example
.PHONY: examples

# Individual example targets
file-only-example:
	cd example/file-only && go build -o ./file-only .

gcs-example:
	cd example/with-gcs && go build -tags gcs -o ./with-gcs .

gcs-example-stub:
	cd example/with-gcs && go build -o ./with-gcs-stub .

comprehensive-example:
	cd example/comprehensive && go build -o ./comprehensive .

# Test targets
test:
	go test ./...
.PHONY: test

test-with-gcs:
	go test -tags gcs ./...
.PHONY: test-with-gcs

# Benchmarks
bench:
	go test -bench=. ./...
.PHONY: bench

# Dependency management
vendor:
	go mod tidy
	go mod vendor
.PHONY: vendor

# Linting
lint:
	golangci-lint run --timeout=20m
.PHONY: lint

lint-with-gcs:
	golangci-lint run --timeout=20m --build-tags "gcs"
.PHONY: lint-with-gcs

# Clean up
clean:
	rm -f example/file-only/file-only example/with-gcs/with-gcs example/with-gcs/with-gcs-stub example/comprehensive/comprehensive
.PHONY: clean

# Help
help:
	@echo "Available targets:"
	@echo "  all                    - Run tests and build all examples"
	@echo "  examples               - Build all examples"
	@echo "  file-only-example      - Build lightweight file-only example"
	@echo "  gcs-example            - Build GCS example with full SDK support"
	@echo "  gcs-example-stub       - Build GCS example in stub mode (no tags)"
	@echo "  comprehensive-example  - Build comprehensive demo"
	@echo "  test                   - Run unit tests"
	@echo "  test-with-gcs          - Run unit tests with GCS build tags"
	@echo "  bench                  - Run benchmarks"
	@echo "  vendor                 - Update dependencies and vendor"
	@echo "  lint                   - Run linter"
	@echo "  lint-with-gcs          - Run linter with GCS build tags"
	@echo "  clean                  - Remove built binaries"
	@echo "  help                   - Show this help"
.PHONY: help
