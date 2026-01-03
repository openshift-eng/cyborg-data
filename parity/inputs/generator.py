"""Generate test inputs from catalog based on parameter names."""

from dataclasses import dataclass
from typing import Any

from .test_data_catalog import TestDataCatalog


@dataclass
class TestCase:
    """A single test case with inputs and expected behavior."""

    name: str  # e.g., "valid", "missing", "invalid"
    inputs: dict[str, Any]  # Parameter name -> value mapping


class TestInputGenerator:
    """Generate test inputs by inferring from parameter names."""

    def __init__(self, catalog: TestDataCatalog) -> None:
        self.catalog = catalog

    def generate_for_params(
        self, params: list[tuple[str, Any]]
    ) -> list[TestCase]:
        """Generate test cases for a method's parameters.

        Args:
            params: List of (param_name, param_type) tuples

        Returns:
            List of TestCase objects covering valid and invalid scenarios
        """
        if not params:
            return [TestCase(name="no_args", inputs={})]

        test_cases: list[TestCase] = []

        valid_inputs: dict[str, Any] = {}
        for param_name, _ in params:
            values = self._get_values_for_param(param_name)
            if values:
                valid_inputs[param_name] = values[0]
            else:
                valid_inputs[param_name] = self._default_value_for_param(param_name)
        test_cases.append(TestCase(name="valid", inputs=valid_inputs))

        missing_inputs: dict[str, Any] = {}
        for param_name, _ in params:
            missing_inputs[param_name] = self._get_invalid_value_for_param(param_name)
        test_cases.append(TestCase(name="missing", inputs=missing_inputs))

        for param_name, _ in params:
            values = self._get_values_for_param(param_name)
            for i, value in enumerate(values[1:3], start=2):  # Up to 2 more values
                extra_inputs = valid_inputs.copy()
                extra_inputs[param_name] = value
                test_cases.append(
                    TestCase(name=f"valid_{param_name}_{i}", inputs=extra_inputs)
                )

        return test_cases

    def _get_values_for_param(self, param_name: str) -> list[Any]:
        """Get valid values for a parameter based on its name."""
        name_lower = param_name.lower()

        if name_lower in ("uid", "employee_uid", "employeeuid", "manager_uid", "manageruid"):
            return self.catalog.employee_uids
        if "email" in name_lower:
            return self.catalog.employee_emails
        if name_lower in ("slack_id", "slackid", "slack_uid", "slackuid"):
            return self.catalog.slack_ids
        if name_lower in ("channel_id", "channelid", "slack_channel_id"):
            return self.catalog.slack_channel_ids
        if name_lower in ("github_id", "githubid"):
            return self.catalog.github_ids
        if name_lower in ("team", "team_name", "teamname"):
            return self.catalog.team_names
        if name_lower in ("org", "org_name", "orgname"):
            return self.catalog.org_names
        if name_lower in ("pillar", "pillar_name", "pillarname"):
            return self.catalog.pillar_names
        if name_lower in ("team_group", "teamgroup", "team_group_name", "teamgroupname"):
            return self.catalog.team_group_names
        if name_lower in ("component", "component_name", "componentname"):
            return self.catalog.component_names
        if name_lower in ("project", "jira_project", "jiraproject"):
            return self.catalog.jira_projects
        if name_lower in ("jira_component", "jiracomponent"):
            return self.catalog.jira_components
        if name_lower == "name":
            return self.catalog.team_names + self.catalog.org_names + self.catalog.pillar_names

        return []

    def _get_invalid_value_for_param(self, param_name: str) -> Any:
        """Get an invalid/missing value for a parameter."""
        name_lower = param_name.lower()

        if name_lower in ("uid", "employee_uid", "employeeuid", "manager_uid"):
            return self.catalog.invalid_uid
        if "email" in name_lower:
            return self.catalog.invalid_email
        if "slack" in name_lower and "id" in name_lower:
            return self.catalog.invalid_slack_id
        if "github" in name_lower:
            return self.catalog.invalid_github_id
        if "team_group" in name_lower or name_lower == "teamgroup":
            return self.catalog.invalid_team_group
        if "team" in name_lower:
            return self.catalog.invalid_team
        if "org" in name_lower:
            return self.catalog.invalid_org
        if "pillar" in name_lower:
            return self.catalog.invalid_pillar
        if "component" in name_lower:
            return self.catalog.invalid_component
        if "project" in name_lower or "jira" in name_lower:
            return self.catalog.invalid_jira_project

        return "invalid-value"

    def _default_value_for_param(self, param_name: str) -> Any:
        """Get a default value when no catalog values are available."""
        name_lower = param_name.lower()
        if name_lower.startswith("is_") or name_lower.startswith("has_"):
            return True
        return "test-value"
