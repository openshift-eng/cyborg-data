#!/usr/bin/env python3
"""
Async example demonstrating orgdatacore with AsyncService.

This example shows how to use the async API with asyncio, which is ideal
for frameworks like FastAPI, aiohttp, Starlette, etc.

Requirements:
    pip install orgdatacore[gcs]
    # or: uv sync --extra gcs

Usage:
    python examples/async_demo.py

    # With custom bucket/path:
    BUCKET=my-bucket OBJECT_PATH=data.json python examples/async_demo.py
"""

import asyncio
import os
from datetime import timedelta

from orgdatacore import (
    AsyncService,
    GCSConfig,
    __version__,
    configure_default_logging,
)

# Check if GCS support is available
from orgdatacore import AsyncGCSDataSource
HAS_GCS = AsyncGCSDataSource is not None


async def main() -> None:
    """Main async entry point."""
    # Enable logging to see what's happening
    configure_default_logging()

    print(f"orgdatacore v{__version__} - Async Demo")
    print("=" * 50)

    if not HAS_GCS:
        print("\nGCS support not installed!")
        print("Install with: pip install orgdatacore[gcs]")
        print("Or with uv:   uv sync --extra gcs")
        return

    # Configuration from environment or defaults (same as gcs_demo.py)
    bucket = os.environ.get("BUCKET", "resolved-org")
    object_path = os.environ.get("OBJECT_PATH", "orgdata/comprehensive_index_dump.json")
    project_id = os.environ.get("PROJECT_ID")

    config = GCSConfig(
        bucket=bucket,
        object_path=object_path,
        project_id=project_id,
        check_interval=timedelta(minutes=5),
    )

    print(f"\nLoading from gs://{bucket}/{object_path}")

    # Create async service and data source
    source = AsyncGCSDataSource(config)
    service = AsyncService()

    # Load data asynchronously
    await service.load_from_data_source(source)

    version = service.get_version()
    print(f"Data loaded: {version.employee_count} employees, {version.org_count} orgs")
    print(f"Load time: {version.load_time}")

    # Health checks
    print(f"\nHealth: {service.is_healthy()}, Ready: {service.is_ready()}")

    # Demo: async lookups
    print("\n" + "=" * 50)
    print("Async Lookup Examples")
    print("=" * 50)

    # Get all teams
    teams = await service.get_all_teams()
    print(f"\nTotal teams: {len(teams)}")
    if teams:
        print(f"First 5: {[t.name for t in teams[:5]]}")

    # Get all orgs
    orgs = await service.get_all_orgs()
    print(f"\nTotal orgs: {len(orgs)}")
    if orgs:
        print(f"First 5: {[o.name for o in orgs[:5]]}")

    # Demo: concurrent lookups (the async advantage!)
    print("\n" + "=" * 50)
    print("Concurrent Lookup Demo")
    print("=" * 50)

    if teams:
        team_names = [t.name for t in teams[:5]]
        print(f"\nFetching members for 5 teams concurrently...")

        # This runs all 5 lookups concurrently!
        results = await asyncio.gather(
            *[service.get_team_members(name) for name in team_names]
        )

        for name, members in zip(team_names, results):
            print(f"   {name}: {len(members)} members")

    # Demo: lookup by different identifiers
    print("\n" + "=" * 50)
    print("Lookup by Identifier")
    print("=" * 50)

    employees = await service.get_all_employees()
    if employees:
        sample = employees[0]
        print(f"\nSample employee: {sample.full_name} ({sample.uid})")

        # These can all run concurrently too
        by_uid, by_email = await asyncio.gather(
            service.get_employee_by_uid(sample.uid),
            service.get_employee_by_email(sample.email),
        )

        print(f"   Found by UID: {by_uid is not None}")
        print(f"   Found by email: {by_email is not None}")

        if sample.slack_uid:
            by_slack = await service.get_employee_by_slack_uid(sample.slack_uid)
            print(f"   Found by Slack UID: {by_slack is not None}")

        if sample.github_id:
            by_github = await service.get_employee_by_github_id(sample.github_id)
            print(f"   Found by GitHub ID: {by_github is not None}")

    print("\nAsync demo complete!")


if __name__ == "__main__":
    asyncio.run(main())

