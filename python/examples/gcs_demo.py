#!/usr/bin/env python3
"""
Demo: Load organizational data from GCS.

This example uses the default GCS configuration from the Go library examples.
Requires google-cloud-storage package: pip install google-cloud-storage

Uses Application Default Credentials (ADC) - make sure you're logged in:
    gcloud auth application-default login
"""

from datetime import timedelta

from orgdatacore.datasources import GCSDataSourceWithSDK

from orgdatacore import GCSConfig, Service


def main():
    print("=== GCS Demo (Python) ===")
    print()

    # Default configuration (same as Go library examples)
    config = GCSConfig(
        bucket="resolved-org",
        object_path="orgdata/comprehensive_index_dump.json",
        project_id="openshift-crt",
        check_interval=timedelta(minutes=5),
    )

    print(f"Loading from gs://{config.bucket}/{config.object_path}")
    print()

    # Create data source and service
    source = GCSDataSourceWithSDK(config)
    service = Service()

    # Load data
    try:
        service.load_from_data_source(source)
    except Exception as e:
        print(f"Failed to load from GCS: {e}")
        print()
        print("Make sure you're authenticated:")
        print("  gcloud auth application-default login")
        return

    # Show version info
    version = service.get_version()
    print("✓ Data loaded successfully!")
    print(f"  Employees: {version.employee_count}")
    print(f"  Organizations: {version.org_count}")
    print(f"  Load time: {version.load_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Demonstrate queries
    print("=== Query Examples ===")
    print()

    # Get statistics
    all_teams = service.get_all_team_names()
    all_orgs = service.get_all_org_names()
    all_pillars = service.get_all_pillar_names()
    all_team_groups = service.get_all_team_group_names()
    all_employees = service.get_all_employee_uids()

    print(f"Total Teams: {len(all_teams)}")
    print(f"Total Organizations: {len(all_orgs)}")
    print(f"Total Pillars: {len(all_pillars)}")
    print(f"Total Team Groups: {len(all_team_groups)}")
    print(f"Total Employees: {len(all_employees)}")
    print()

    # Sample some data
    if all_teams:
        print(f"Sample teams: {all_teams[:5]}")
    if all_orgs:
        print(f"Sample orgs: {all_orgs[:5]}")
    print()

    # Try to get a sample employee
    if all_employees:
        sample_uid = all_employees[0]
        emp = service.get_employee_by_uid(sample_uid)
        if emp:
            print("Sample employee:")
            print(f"  UID: {emp.uid}")
            print(f"  Name: {emp.full_name}")
            print(f"  Email: {emp.email}")
            print(f"  Job Title: {emp.job_title}")
            if emp.slack_uid:
                print(f"  Slack UID: {emp.slack_uid}")
            if emp.github_id:
                print(f"  GitHub ID: {emp.github_id}")
            print()

            # Get their teams
            teams = service.get_teams_for_uid(sample_uid)
            if teams:
                print(f"  Teams: {teams}")

            # Get their organizations
            if emp.slack_uid:
                orgs = service.get_user_organizations(emp.slack_uid)
                if orgs:
                    print("  Organizations:")
                    for org in orgs[:10]:  # Show first 10
                        print(f"    - {org.name} ({org.type})")
            print()

    # Sample team lookup
    if all_teams:
        sample_team = all_teams[0]
        team = service.get_team_by_name(sample_team)
        if team:
            print(f"Sample team: {team.name}")
            members = service.get_team_members(sample_team)
            print(f"  Members: {len(members)}")
            if members:
                print(f"  Sample member: {members[0].full_name}")

    print()
    print("=== Demo Complete ===")


if __name__ == "__main__":
    main()
