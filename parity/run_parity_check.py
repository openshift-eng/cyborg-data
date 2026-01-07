#!/usr/bin/env python3
"""Dynamic API Parity Check Orchestrator.

This script automatically discovers API methods in both Go and Python,
generates test inputs from test data, runs both implementations, and
compares outputs.

Exit codes:
- 0: All parity checks passed
- 1: Parity failures detected
- 2: Infrastructure error
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PARITY_ROOT = Path(__file__).parent
REPO_ROOT = PARITY_ROOT.parent
sys.path.insert(0, str(PARITY_ROOT))
sys.path.insert(0, str(REPO_ROOT / "python"))

from discovery import normalize, parse_go_interface  # noqa: E402
from discovery.python_introspector import (  # noqa: E402
    EXCLUDED_METHODS,
    introspect_python_service,
)
from inputs import TestInputGenerator, load_catalog  # noqa: E402


def main() -> int:
    """Run parity check and return exit code."""
    print("=" * 60)
    print("Dynamic API Parity Check")
    print("=" * 60)
    print()

    go_interface_path = REPO_ROOT / "go" / "interface.go"
    test_data_path = REPO_ROOT / "testdata" / "test_org_data.json"
    go_runner_path = PARITY_ROOT / "go_runner"
    python_runner_path = PARITY_ROOT / "python_runner" / "runner.py"

    print("Step 1: Discovering API methods...")
    try:
        go_methods = parse_go_interface(go_interface_path)
        python_methods = introspect_python_service(REPO_ROOT / "python")
    except Exception as e:
        print(f"ERROR: Failed to discover methods: {e}")
        return 2

    print(f"  Found {len(go_methods)} Go methods")
    print(f"  Found {len(python_methods)} Python methods")
    print()

    print("Step 2: Checking method parity...")
    # Build maps from normalized name -> original name
    # Exclude lifecycle/time-dependent methods from both sides
    excluded_normalized = {normalize(name) for name in EXCLUDED_METHODS}

    go_by_normalized: dict[str, str] = {}
    for m in go_methods:
        norm = normalize(m.name)
        if norm not in excluded_normalized:
            go_by_normalized[norm] = m.name

    python_by_normalized: dict[str, str] = {}
    for m in python_methods:
        norm = normalize(m.name)
        if norm not in excluded_normalized:
            python_by_normalized[norm] = m.name

    go_testable = len(go_by_normalized)
    py_testable = len(python_by_normalized)
    print(f"  Comparable methods: {go_testable} Go, {py_testable} Python")

    # Find mismatches
    go_only = set(go_by_normalized.keys()) - set(python_by_normalized.keys())
    python_only = set(python_by_normalized.keys()) - set(go_by_normalized.keys())

    parity_issues = []
    for norm in sorted(go_only):
        go_name = go_by_normalized[norm]
        parity_issues.append(f"  - Missing in Python: {go_name}")

    for norm in sorted(python_only):
        py_name = python_by_normalized[norm]
        parity_issues.append(f"  - Missing in Go: {py_name}")

    if parity_issues:
        print("PARITY FAILURE: Method parity issues detected:")
        for issue in parity_issues:
            print(issue)
        print()
        return 1

    print("Step 3: Generating test inputs...")
    catalog = load_catalog(test_data_path)
    generator = TestInputGenerator(catalog)

    # Match Go and Python methods by normalized name
    go_methods_by_name = {m.name: m for m in go_methods}
    python_methods_by_name = {m.name: m for m in python_methods}

    testable_methods = []
    for norm, go_name in go_by_normalized.items():
        if norm in python_by_normalized:
            py_name = python_by_normalized[norm]
            testable_methods.append((go_methods_by_name[go_name], python_methods_by_name[py_name]))

    print(f"  Testable methods: {len(testable_methods)}")
    print()

    method_test_cases = []
    for go_method, python_method in testable_methods:
        test_cases = generator.generate_for_params(python_method.params)
        method_test_cases.append({
            "go_name": go_method.name,
            "python_name": python_method.name,
            "test_cases": [{"name": tc.name, "inputs": tc.inputs} for tc in test_cases],
        })

    print("Step 4: Running Go implementation...")
    go_config = {
        "test_data_path": str(test_data_path),
        "methods": method_test_cases,
    }

    try:
        go_results = run_go_runner(go_runner_path, go_config)
    except Exception as e:
        print(f"ERROR: Go runner failed: {e}")
        return 2

    print(f"  Got {len(go_results)} results")
    print()

    print("Step 5: Running Python implementation...")
    python_config = {
        "test_data_path": str(test_data_path),
        "methods": method_test_cases,
    }

    try:
        python_results = run_python_runner(python_runner_path, python_config)
    except Exception as e:
        print(f"ERROR: Python runner failed: {e}")
        return 2

    print(f"  Got {len(python_results)} results")
    print()

    print("Step 6: Comparing outputs...")
    failures = compare_results(go_results, python_results, method_test_cases)

    if failures:
        print()
        print("=" * 60)
        print(f"FAILED: {len(failures)} parity failures detected")
        print("=" * 60)
        for failure in failures[:20]:
            print(failure)
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more failures")
        return 1

    print()
    print("=" * 60)
    print("PASSED: All parity checks successful")
    print("=" * 60)
    return 0


def run_go_runner(runner_path: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Run the Go test runner and return results."""
    build_result = subprocess.run(
        ["go", "build", "-mod=mod", "-o", "runner", "."],
        cwd=runner_path,
        capture_output=True,
        text=True,
    )
    if build_result.returncode != 0:
        raise RuntimeError(f"Go build failed: {build_result.stderr}")

    result = subprocess.run(
        [str(runner_path / "runner")],
        input=json.dumps(config),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Go runner failed: {result.stderr}")

    return json.loads(result.stdout)


def run_python_runner(
    runner_path: Path, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run the Python test runner and return results."""
    result = subprocess.run(
        [sys.executable, str(runner_path)],
        input=json.dumps(config),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Python runner failed: {result.stderr}")

    return json.loads(result.stdout)


def compare_results(
    go_results: list[dict[str, Any]],
    python_results: list[dict[str, Any]],
    method_specs: list[dict[str, Any]],
) -> list[str]:
    """Compare Go and Python results, return list of failure messages."""
    failures = []

    go_by_key: dict[str, dict[str, Any]] = {}
    for r in go_results:
        go_by_key[f"{r['method_go_name']}:{r['case_name']}"] = r

    python_by_key: dict[str, dict[str, Any]] = {}
    for r in python_results:
        python_by_key[f"{r['method_python_name']}:{r['case_name']}"] = r

    for spec in method_specs:
        go_name = spec["go_name"]
        python_name = spec["python_name"]

        for tc in spec["test_cases"]:
            case_name = tc["name"]
            go_key = f"{go_name}:{case_name}"
            py_key = f"{python_name}:{case_name}"

            go_result = go_by_key.get(go_key)
            py_result = python_by_key.get(py_key)

            if go_result is None:
                failures.append(f"  {go_name}/{case_name}: Missing Go result")
                continue
            if py_result is None:
                failures.append(f"  {python_name}/{case_name}: Missing Python result")
                continue

            go_error = go_result.get("error", "")
            py_error = py_result.get("error", "")

            if go_error and py_error:
                continue
            if go_error and not py_error:
                failures.append(
                    f"  {go_name}/{case_name}: Go errored but Python succeeded\n"
                    f"    Go error: {go_error}"
                )
                continue
            if py_error and not go_error:
                failures.append(
                    f"  {go_name}/{case_name}: Python errored but Go succeeded\n"
                    f"    Python error: {py_error}"
                )
                continue

            go_output = normalize_output(go_result.get("output"))
            py_output = normalize_output(py_result.get("output"))

            if go_output != py_output:
                failures.append(
                    f"  {go_name}/{case_name}: Output mismatch\n"
                    f"    Go:     {json.dumps(go_output, sort_keys=True)}\n"
                    f"    Python: {json.dumps(py_output, sort_keys=True)}"
                )

    return failures


def normalize_output(output: Any) -> Any:
    """Normalize output for comparison."""
    if output is None:
        return None
    if isinstance(output, bool):
        return output
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return [normalize_output(item) for item in output]
    if isinstance(output, dict):
        return {k: normalize_output(v) for k, v in sorted(output.items())}
    return output


if __name__ == "__main__":
    sys.exit(main())
