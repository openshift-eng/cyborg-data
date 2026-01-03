"""Name mapping between Go PascalCase and Python snake_case."""

import re

# Acronyms that should be kept together
ACRONYMS = {"uid", "id", "gcs", "api", "url", "uri", "json", "xml", "html", "http", "https", "github"}

# Compound words that need special handling (Go version -> replacement before splitting)
COMPOUND_WORDS = {
    "GitHub": "Github",  # Treat as single word, not Git_Hub
}


def go_to_python(go_name: str) -> str:
    """Convert GoPascalCase to python_snake_case.

    Examples:
        GetEmployeeByUID -> get_employee_by_uid
        IsSlackUserInTeam -> is_slack_user_in_team
        GetGCSConfig -> get_gcs_config
        GetEmployeeByGitHubID -> get_employee_by_github_id
    """
    # Handle compound words first
    name = go_name
    for go_compound, replacement in COMPOUND_WORDS.items():
        name = name.replace(go_compound, replacement)

    # Insert underscore before uppercase letters
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()


def python_to_go(python_name: str) -> str:
    """Convert python_snake_case to GoPascalCase.

    Examples:
        get_employee_by_uid -> GetEmployeeByUID
        is_slack_user_in_team -> IsSlackUserInTeam
        get_gcs_config -> GetGCSConfig
        get_employee_by_github_id -> GetEmployeeByGitHubID
    """
    components = python_name.split('_')
    result = []
    for component in components:
        if component.lower() in ACRONYMS:
            # Special handling for 'github' -> 'GitHub'
            if component.lower() == "github":
                result.append("GitHub")
            else:
                result.append(component.upper())
        else:
            result.append(component.capitalize())
    return ''.join(result)
