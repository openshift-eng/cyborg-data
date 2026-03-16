"""Internal serialization: Data model -> dict/JSON bytes.

Not part of the public API. Used by PII decorators and test helpers
to round-trip typed Data through JSON without raw dict manipulation.
"""

import json
from typing import Any

from ._types import (
    Component,
    Data,
    Employee,
    Group,
    Org,
    Pillar,
    Team,
    TeamGroup,
)


def data_to_dict(data: Data) -> dict[str, Any]:
    """Convert Data to dictionary for JSON serialization."""
    result: dict[str, Any] = {
        "metadata": data.metadata.model_dump(),
        "lookups": {
            "employees": {
                k: employee_to_dict(v) for k, v in data.lookups.employees.items()
            },
            "teams": {k: entity_to_dict(v) for k, v in data.lookups.teams.items()},
            "orgs": {k: entity_to_dict(v) for k, v in data.lookups.orgs.items()},
            "pillars": {k: entity_to_dict(v) for k, v in data.lookups.pillars.items()},
            "team_groups": {
                k: entity_to_dict(v) for k, v in data.lookups.team_groups.items()
            },
            "components": {
                k: component_to_dict(v) for k, v in data.lookups.components.items()
            },
        },
        "indexes": {
            "membership": {
                "membership_index": {
                    k: [m.model_dump() for m in v]
                    for k, v in data.indexes.membership.membership_index.items()
                },
            },
            "slack_id_mappings": {
                "slack_uid_to_uid": dict(
                    data.indexes.slack_id_mappings.slack_uid_to_uid
                ),
            },
            "github_id_mappings": {
                "github_id_to_uid": dict(
                    data.indexes.github_id_mappings.github_id_to_uid
                ),
            },
        },
    }
    # Add jira index if present
    if data.indexes.jira.project_component_owners:
        result["indexes"]["jira"] = {
            project: {
                component: [o.model_dump() for o in owners]
                for component, owners in components.items()
            }
            for project, components in data.indexes.jira.project_component_owners.items()
        }
    if data.indexes.component_ownership.component_owners:
        result["indexes"]["component_ownership"] = {
            component_name: [o.model_dump() for o in owners]
            for component_name, owners in data.indexes.component_ownership.component_owners.items()
        }
    return result


def data_to_json_bytes(data: Data) -> bytes:
    """Convert Data to JSON bytes."""
    return json.dumps(data_to_dict(data)).encode("utf-8")


def component_to_dict(component: Component) -> dict[str, Any]:
    """Convert Component to dictionary using the nested indexer format."""
    d: dict[str, Any] = {
        "name": component.name,
    }
    if component.description:
        d["description"] = component.description
    # Write type/repos under nested "component" key to match indexer format
    nested: dict[str, Any] = {}
    if component.type:
        nested["type"] = {"name": component.type}
    if component.repos:
        nested["repos"] = [r.model_dump(by_alias=True) for r in component.repos]
    if component.jiras:
        nested["jiras"] = [j.model_dump() for j in component.jiras]
    if component.repos_list:
        nested["repos_list"] = list(component.repos_list)
    if nested:
        d["component"] = nested
    if component.parent:
        d["parent"] = component.parent.model_dump()
    if component.parent_path:
        d["parent_path"] = component.parent_path
    return d


def employee_to_dict(emp: Employee) -> dict[str, Any]:
    """Convert Employee to dictionary with conditional includes."""
    d: dict[str, Any] = {
        "uid": emp.uid,
        "full_name": emp.full_name,
        "email": emp.email,
        "job_title": emp.job_title,
    }
    if emp.slack_uid:
        d["slack_uid"] = emp.slack_uid
    if emp.github_id:
        d["github_id"] = emp.github_id
    if emp.rhat_geo:
        d["rhat_geo"] = emp.rhat_geo
    if emp.cost_center:
        d["cost_center"] = emp.cost_center
    if emp.manager_uid:
        d["manager_uid"] = emp.manager_uid
    d["is_people_manager"] = emp.is_people_manager
    if emp.timezone:
        d["timezone"] = emp.timezone
    return d


def group_to_dict(group: Group) -> dict[str, Any]:
    """Convert Group to dictionary with conditional includes."""
    d: dict[str, Any] = {
        "type": group.type.model_dump(),
        "resolved_people_uid_list": list(group.resolved_people_uid_list),
    }
    if group.slack:
        d["slack"] = group.slack.model_dump()
    if group.roles:
        d["resolved_roles"] = [r.model_dump() for r in group.roles]
    if group.jiras:
        d["jiras"] = [j.model_dump() for j in group.jiras]
    if group.repos:
        d["repos"] = [r.model_dump(by_alias=True) for r in group.repos]
    if group.keywords:
        d["keywords"] = list(group.keywords)
    if group.emails:
        d["emails"] = [e.model_dump() for e in group.emails]
    if group.resources:
        d["resources"] = [r.model_dump() for r in group.resources]
    if group.escalation:
        d["escalation"] = [e.model_dump() for e in group.escalation]
    if group.component_roles:
        d["component_roles"] = list(group.component_roles)
    return d


def entity_to_dict(entity: Team | Org | Pillar | TeamGroup) -> dict[str, Any]:
    """Convert a Team/Org/Pillar/TeamGroup to dictionary."""
    d: dict[str, Any] = {
        "uid": entity.uid,
        "name": entity.name,
        "type": entity.type,
        "group": group_to_dict(entity.group),
    }
    if entity.tab_name:
        d["tab_name"] = entity.tab_name
    if entity.description:
        d["description"] = entity.description
    if entity.parent:
        d["parent"] = entity.parent.model_dump()
    return d
