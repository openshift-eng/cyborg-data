# Multi-Language Build System for cyborg-data
# Compatible with OpenShift Prow CI
#
# Prow can invoke these targets directly:
#   make go-test      - Run Go unit tests (Prow job: unit-go)
#   make python-test  - Run Python unit tests (Prow job: unit-python)
#   make test         - Run all tests

.PHONY: all test lint clean help go-test python-test go-lint python-lint go-build python-build python-typing

# Default target
all: test

PYTHON ?= python

help:
	@echo "Multi-Language Build System for cyborg-data"
	@echo ""
	@echo "Available targets:"
	@echo "  make test          - Run tests for both Go and Python"
	@echo "  make lint          - Run linters for both Go and Python"
	@echo "  make build         - Build examples for both languages"
	@echo "  make clean         - Clean build artifacts"
	@echo ""
	@echo "Go-specific targets:"
	@echo "  make go-test       - Run Go tests"
	@echo "  make go-lint       - Run Go linter"
	@echo "  make go-build      - Build Go examples"
	@echo ""
	@echo "Python-specific targets:"
	@echo "  make python-test   - Run Python tests"
	@echo "  make python-lint   - Run Python linter"
	@echo "  make python-typing - Run Python type checker (mypy strict)"
	@echo "  make python-build  - Build Python package"

# Combined targets
test: go-test python-test
	@echo "✅ All tests passed (Go + Python)"

lint: go-lint python-lint
	@echo "✅ All linters passed (Go + Python)"

build: go-build python-build
	@echo "✅ All builds completed (Go + Python)"

clean: go-clean python-clean
	@echo "✅ All artifacts cleaned"

# Go targets
go-test:
	@echo "Running Go tests..."
	cd go && $(MAKE) test

go-test-with-gcs:
	@echo "Running Go tests with GCS support..."
	cd go && $(MAKE) test-with-gcs

go-lint:
	@echo "Running Go linter..."
	cd go && $(MAKE) lint

go-build:
	@echo "Building Go examples..."
	cd go && $(MAKE) examples

go-clean:
	@echo "Cleaning Go build artifacts..."
	cd go && $(MAKE) clean

go-bench:
	@echo "Running Go benchmarks..."
	cd go && $(MAKE) bench

# Python targets
python-test:
	@echo "Running Python tests..."
	cd python && pytest

python-lint:
	@echo "Running Python linter..."
	cd python && ruff check .

python-typing:
	@echo "Running Python type checker (mypy strict)..."
	cd python && $(PYTHON) -m mypy orgdatacore

python-format:
	@echo "Formatting Python code..."
	cd python && ruff format .

python-build:
	@echo "Building Python package..."
	cd python && uv build

python-clean:
	@echo "Cleaning Python build artifacts..."
	cd python && rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache __pycache__

# Validation targets
validate-parity:
	@echo "Validating API parity between Go and Python..."
	@./scripts/validate-api-parity.sh || echo "Parity validation script not yet implemented"

# Documentation targets
docs:
	@echo "Building documentation..."
	@echo "Documentation build not yet configured"
