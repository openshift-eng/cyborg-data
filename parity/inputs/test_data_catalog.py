"""Test data catalog for extracting test values from test_org_data.json."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TestDataCatalog:
    """Catalog of test values extracted from test data."""

    employee_uids: list[str] = field(default_factory=list)
    employee_emails: list[str] = field(default_factory=list)
    slack_ids: list[str] = field(default_factory=list)
    github_ids: list[str] = field(default_factory=list)
    team_names: list[str] = field(default_factory=list)
    org_names: list[str] = field(default_factory=list)
    pillar_names: list[str] = field(default_factory=list)
    team_group_names: list[str] = field(default_factory=list)
    component_names: list[str] = field(default_factory=list)
    jira_projects: list[str] = field(default_factory=list)
    jira_components: list[str] = field(default_factory=list)
    slack_channels: list[str] = field(default_factory=list)
    slack_channel_ids: list[str] = field(default_factory=list)
    invalid_uid: str = "nonexistent-user-xyz"
    invalid_email: str = "nobody@nowhere.invalid"
    invalid_slack_id: str = "UINVALID999"
    invalid_github_id: str = "nonexistent-github-user"
    invalid_team: str = "nonexistent-team-xyz"
    invalid_org: str = "nonexistent-org-xyz"
    invalid_pillar: str = "nonexistent-pillar-xyz"
    invalid_team_group: str = "nonexistent-team-group-xyz"
    invalid_component: str = "nonexistent-component-xyz"
    invalid_jira_project: str = "INVALID"
    raw_data: dict[str, Any] = field(default_factory=dict)


def load_catalog(test_data_path: Path) -> TestDataCatalog:
    """Load test data and extract catalog of test values.

    Args:
        test_data_path: Path to test_org_data.json

    Returns:
        TestDataCatalog with extracted values
    """
    with open(test_data_path) as f:
        data = json.load(f)

    catalog = TestDataCatalog(raw_data=data)
    lookups = data.get("lookups", {})
    indexes = data.get("indexes", {})

    for uid, emp in lookups.get("employees", {}).items():
        catalog.employee_uids.append(uid)
        if email := emp.get("email"):
            catalog.employee_emails.append(email)

    catalog.slack_ids = list(
        indexes.get("slack_id_mappings", {}).get("slack_uid_to_uid", {}).keys()
    )
    catalog.github_ids = list(
        indexes.get("github_id_mappings", {}).get("github_id_to_uid", {}).keys()
    )

    teams = lookups.get("teams", {})
    catalog.team_names = list(teams.keys())
    for team in teams.values():
        for channel in team.get("group", {}).get("slack", {}).get("channels", []):
            if ch_name := channel.get("channel"):
                catalog.slack_channels.append(ch_name)
            if ch_id := channel.get("channel_id"):
                catalog.slack_channel_ids.append(ch_id)

    catalog.org_names = list(lookups.get("orgs", {}).keys())
    catalog.pillar_names = list(lookups.get("pillars", {}).keys())
    catalog.team_group_names = list(lookups.get("team_groups", {}).keys())
    catalog.component_names = list(lookups.get("components", {}).keys())

    for project, components_map in indexes.get("jira", {}).items():
        catalog.jira_projects.append(project)
        for component_name in components_map.keys():
            if component_name != "_project_level":
                catalog.jira_components.append(component_name)

    return catalog
