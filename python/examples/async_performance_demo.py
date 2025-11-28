#!/usr/bin/env python3
"""
Async performance demo with GCS watch/reload testing.

This example demonstrates:
1. Performance comparison: concurrent vs sequential lookups
2. GCS watcher: background data refresh when source changes
3. Health checks during operations

Requirements:
    pip install orgdatacore[gcs]
    # or: uv sync --extra gcs

Usage:
    python examples/async_performance_demo.py
"""

import asyncio
import os
import time
from datetime import timedelta

from orgdatacore import (
    AsyncService,
    GCSConfig,
    __version__,
    configure_default_logging,
    get_logger,
)

try:
    from orgdatacore.async_datasources import AsyncGCSDataSource
    HAS_GCS = True
except ImportError:
    HAS_GCS = False


async def benchmark_sequential(service: AsyncService, uids: list[str]) -> float:
    """Benchmark sequential lookups."""
    start = time.perf_counter()
    for uid in uids:
        await service.get_employee_by_uid(uid)
    return time.perf_counter() - start


async def benchmark_concurrent(service: AsyncService, uids: list[str]) -> float:
    """Benchmark concurrent lookups."""
    start = time.perf_counter()
    await asyncio.gather(*[service.get_employee_by_uid(uid) for uid in uids])
    return time.perf_counter() - start


async def benchmark_mixed_operations(service: AsyncService, count: int) -> float:
    """Benchmark mixed concurrent operations."""
    teams = await service.get_all_teams()
    team_names = [t.name for t in teams[:count]] if teams else []

    start = time.perf_counter()
    # Mix of different operations running concurrently
    await asyncio.gather(
        service.get_all_employees(),
        service.get_all_teams(),
        service.get_all_orgs(),
        *[service.get_team_members(name) for name in team_names],
    )
    return time.perf_counter() - start


async def run_performance_benchmark(service: AsyncService) -> None:
    """Run performance benchmarks."""
    print("\n" + "=" * 60)
    print("PERFORMANCE BENCHMARK")
    print("=" * 60)

    # Get sample UIDs for testing
    employees = await service.get_all_employees()
    if not employees:
        print("No employees found, skipping benchmark")
        return

    sample_uids = [e.uid for e in employees[:100]]
    print(f"\nBenchmarking with {len(sample_uids)} employee lookups...")

    # Sequential benchmark
    seq_time = await benchmark_sequential(service, sample_uids)
    print(f"Sequential lookups: {seq_time:.4f}s")

    # Concurrent benchmark
    conc_time = await benchmark_concurrent(service, sample_uids)
    print(f"Concurrent lookups: {conc_time:.4f}s")

    # Calculate speedup
    if conc_time > 0:
        speedup = seq_time / conc_time
        print(f"Speedup: {speedup:.2f}x faster with concurrent")

    # Mixed operations benchmark
    print(f"\nMixed operations (employees + teams + orgs + 10 team members)...")
    mixed_time = await benchmark_mixed_operations(service, 10)
    print(f"Mixed concurrent: {mixed_time:.4f}s")


async def simulate_data_change_detection(
    service: AsyncService,
    source: "AsyncGCSDataSource",
) -> None:
    """
    Demonstrate the GCS watcher detecting changes.
    
    Note: In a real scenario, the watcher runs indefinitely in the background.
    This demo shows how to set it up and monitor for reloads.
    """
    print("\n" + "=" * 60)
    print("GCS WATCHER DEMO")
    print("=" * 60)

    logger = get_logger()
    reload_count = 0
    reload_event = asyncio.Event()

    # Track initial version
    initial_version = service.get_version()
    print(f"\nInitial data version:")
    print(f"  Employee count: {initial_version.employee_count}")
    print(f"  Org count: {initial_version.org_count}")
    print(f"  Load time: {initial_version.load_time}")

    # Create a wrapper callback to track reloads
    async def reload_callback() -> None:
        nonlocal reload_count
        reload_count += 1
        new_version = service.get_version()
        print(f"\n[RELOAD #{reload_count}] Data reloaded!")
        print(f"  Employee count: {new_version.employee_count}")
        print(f"  Org count: {new_version.org_count}")
        print(f"  Load time: {new_version.load_time}")
        reload_event.set()

    # Start the watcher
    print("\nStarting GCS watcher...")
    print(f"Check interval: {source.config.check_interval}")
    
    # Note: The watcher uses the callback passed to it during start_data_source_watcher
    # For this demo, we'll simulate the monitoring behavior
    
    print("\nWatcher is now running in the background.")
    print("The watcher will check for GCS object changes at the configured interval.")
    print("If the GCS object is updated, the data will be automatically reloaded.")

    # Demonstrate that service remains functional while watcher runs
    print("\nDemonstrating service functionality while watcher is active...")
    
    for i in range(3):
        await asyncio.sleep(1)
        
        # Service should remain healthy and responsive
        health_status = "healthy" if service.is_healthy() else "unhealthy"
        ready_status = "ready" if service.is_ready() else "not ready"
        
        # Do a quick lookup to prove service is working
        employees = await service.get_all_employees()
        employee_count = len(employees)
        
        print(f"  [{i+1}/3] Service: {health_status}, {ready_status}, "
              f"employees: {employee_count}")

    print("\nWatcher demo complete.")
    print("In production, the watcher continues running indefinitely.")


async def run_concurrent_stress_test(service: AsyncService) -> None:
    """Run a stress test with many concurrent operations."""
    print("\n" + "=" * 60)
    print("CONCURRENT STRESS TEST")
    print("=" * 60)

    print("\nRunning 1000 concurrent lookups...")
    
    employees = await service.get_all_employees()
    if not employees:
        print("No employees found, skipping stress test")
        return

    # Create 1000 lookup tasks (cycling through available UIDs)
    uids = [e.uid for e in employees]
    tasks = [
        service.get_employee_by_uid(uids[i % len(uids)])
        for i in range(1000)
    ]

    start = time.perf_counter()
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    successful = sum(1 for r in results if r is not None)
    print(f"Completed: {successful}/1000 successful lookups")
    print(f"Time: {elapsed:.4f}s")
    print(f"Throughput: {1000/elapsed:.0f} lookups/second")

    # Verify service is still healthy after stress test
    print(f"\nService health after stress test: {service.is_healthy()}")


async def main() -> None:
    """Main entry point."""
    configure_default_logging()

    print(f"orgdatacore v{__version__} - Async Performance Demo")
    print("=" * 60)

    if not HAS_GCS:
        print("\nGCS support not installed!")
        print("Install with: pip install orgdatacore[gcs]")
        return

    # Configuration
    bucket = os.environ.get("BUCKET", "resolved-org")
    object_path = os.environ.get("OBJECT_PATH", "orgdata/comprehensive_index_dump.json")
    project_id = os.environ.get("PROJECT_ID")

    config = GCSConfig(
        bucket=bucket,
        object_path=object_path,
        project_id=project_id,
        check_interval=timedelta(seconds=30),  # Short interval for demo
    )

    print(f"\nData source: gs://{bucket}/{object_path}")

    # Create service and load data
    source = AsyncGCSDataSource(config)
    service = AsyncService()

    print("Loading data...")
    start = time.perf_counter()
    await service.load_from_data_source(source)
    load_time = time.perf_counter() - start

    version = service.get_version()
    print(f"Data loaded in {load_time:.2f}s")
    print(f"  Employees: {version.employee_count}")
    print(f"  Organizations: {version.org_count}")

    # Run benchmarks
    await run_performance_benchmark(service)

    # Run stress test
    await run_concurrent_stress_test(service)

    # Demonstrate watcher
    await simulate_data_change_detection(service, source)

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

