#!/bin/bash
# Dynamic API Parity Check
# Validates that Go and Python implementations produce identical outputs.
#
# Exit codes:
#   0 - All parity checks passed
#   1 - Parity failures detected
#   2 - Infrastructure error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

# Run the parity check orchestrator
# Use PYTHON env var if set (CI sets python3.12), otherwise default to python3
${PYTHON:-python3} parity/run_parity_check.py
