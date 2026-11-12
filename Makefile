# Multi-Language Build System for cyborg-data
# Compatible with OpenShift Prow CI
#
# Prow can invoke these targets directly:
#   make go-test      - Run Go unit tests (Prow job: unit-go)
#   make python-test  - Run Python unit tests (Prow job: unit-python)
#   make test         - Run all tests

.PHONY: all test lint clean help go-test python-test go-lint python-lint go-build python-build python-typing release-python

# Default target
all: test

# Python interpreter/runner for the python targets. Defaults to `uv run python`,
# which syncs the project environment (including the git-sourced orgindex-schema
# dependency) before executing. CI or environments that already provide an
# interpreter with the deps installed can override, e.g. `make PYTHON=python3.12`.
PYTHON ?= uv run python

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
	@echo "  make go-test-with-gcs - Run Go tests with GCS support"
	@echo "  make go-lint       - Run Go linter"
	@echo "  make go-build      - Build Go examples"
	@echo "  make go-bench      - Run Go benchmarks"
	@echo ""
	@echo "Python-specific targets:"
	@echo "  make python-test   - Run Python tests"
	@echo "  make python-lint   - Run Python linter"
	@echo "  make python-typing - Run Python type checker (mypy strict)"
	@echo "  make python-format - Format Python code with ruff"
	@echo "  make python-build  - Build Python package"
	@echo ""
	@echo "Release targets:"
	@echo "  make release-python VERSION=X.Y.Z - Cut & push a python-vX.Y.Z release tag"
	@echo "                                      (rcN -> TestPyPI, final -> PyPI). See python/RELEASING.md"
	@echo ""
	@echo "Validation targets:"
	@echo "  make validate-parity - Validate API parity between Go and Python"
	@echo "  make docs            - Build documentation"

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

# Python targets (run through $(PYTHON); see its definition above)
python-test:
	@echo "Running Python tests..."
	cd python && $(PYTHON) -m pytest

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

validate-parity:
	@echo "Validating API parity between Go and Python..."
	@./scripts/validate-api-parity.sh

docs: #todo
	@echo "Building documentation..."
	@echo "Documentation build not yet configured"

# Cut a tag-driven release of the Python package (see python/RELEASING.md).
# Routes rcN -> TestPyPI and final -> PyPI (reviewer-gated). Pass extra flags via
# RELEASE_ARGS, e.g. `make release-python VERSION=0.2.0 RELEASE_ARGS=--dry-run`.
release-python:
	@test -n "$(VERSION)" || { \
		echo "Usage: make release-python VERSION=<X.Y.Z[rcN]>   (e.g. 0.1.0, 0.2.0rc1)"; \
		echo "       Options / preview: ./scripts/release.sh --help"; \
		exit 2; }
	@./scripts/release.sh $(RELEASE_ARGS) $(VERSION)
