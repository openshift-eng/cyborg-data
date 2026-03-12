"""Internal serialization: Data dataclass → dict/JSON bytes.

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
        "metadata": {
            "generated_at": data.metadata.generated_at,
            "data_version": data.metadata.data_version,
            "total_employees": data.metadata.total_employees,
            "total_orgs": data.metadata.total_orgs,
            "total_teams": data.metadata.total_teams,
        },
        "lookups": {
            "employees": {
                k: employee_to_dict(v) for k, v in data.lookups.employees.items()
            },
            "teams": {k: team_to_dict(v) for k, v in data.lookups.teams.items()},
            "orgs": {k: org_to_dict(v) for k, v in data.lookups.orgs.items()},
            "pillars": {
                k: pillar_to_dict(v) for k, v in data.lookups.pillars.items()
            },
            "team_groups": {
                k: team_group_to_dict(v)
                for k, v in data.lookups.team_groups.items()
            },
            "components": {
                k: component_to_dict(v) for k, v in data.lookups.components.items()
            },
        },
        "indexes": {
            "membership": {
                "membership_index": {
                    k: [{"name": m.name, "type": m.type} for m in v]
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
                component: [{"name": o.name, "type": o.type} for o in owners]
                for component, owners in components.items()
            }
            for project, components in data.indexes.jira.project_component_owners.items()
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
        nested["repos"] = [
            {
                "repo_name": r.repo,
                "description": r.description,
                "tags": list(r.tags),
                "path": r.path,
                "roles": list(r.roles),
                "branch": r.branch,
                "types": list(r.types),
            }
            for r in component.repos
        ]
    if component.jiras:
        nested["jiras"] = [
            {
                "project": j.project,
                "component": j.component,
                "description": j.description,
                "view": j.view,
                "types": list(j.types),
            }
            for j in component.jiras
        ]
    if component.repos_list:
        nested["repos_list"] = list(component.repos_list)
    if nested:
        d["component"] = nested
    if component.parent:
        d["parent"] = {"name": component.parent.name, "type": component.parent.type}
    if component.parent_path:
        d["parent_path"] = component.parent_path
    return d


def employee_to_dict(emp: Employee) -> dict[str, Any]:
    """Convert Employee to dictionary."""
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
    """Convert Group to dictionary."""
    d: dict[str, Any] = {
        "type": {"name": group.type.name},
        "resolved_people_uid_list": list(group.resolved_people_uid_list),
    }
    if group.slack:
        d["slack"] = {
            "channels": [
                {
                    "channel": c.channel,
                    "channel_id": c.channel_id,
                    "description": c.description,
                    "types": list(c.types),
                }
                for c in group.slack.channels
            ],
            "aliases": [
                {"alias": a.alias, "description": a.description}
                for a in group.slack.aliases
            ],
        }
    if group.roles:
        roles_list = []
        for r in group.roles:
            role_d: dict[str, Any] = {"people": list(r.people), "roles": list(r.roles)}
            if r.description:
                role_d["description"] = r.description
            roles_list.append(role_d)
        d["resolved_roles"] = roles_list
    if group.jiras:
        d["jiras"] = [
            {
                "project": j.project,
                "component": j.component,
                "description": j.description,
                "view": j.view,
                "types": list(j.types),
            }
            for j in group.jiras
        ]
    if group.repos:
        d["repos"] = [
            {
                "repo_name": r.repo,
                "description": r.description,
                "tags": list(r.tags),
                "path": r.path,
                "roles": list(r.roles),
                "branch": r.branch,
                "types": list(r.types),
            }
            for r in group.repos
        ]
    if group.keywords:
        d["keywords"] = list(group.keywords)
    if group.emails:
        d["emails"] = [
            {"address": e.address, "name": e.name, "description": e.description}
            for e in group.emails
        ]
    if group.resources:
        d["resources"] = [
            {"name": r.name, "url": r.url, "description": r.description}
            for r in group.resources
        ]
    if group.component_roles:
        d["component_roles"] = [
            {"component": c.component, "types": list(c.types)}
            for c in group.component_roles
        ]
    return d


def team_to_dict(team: Team) -> dict[str, Any]:
    """Convert Team to dictionary."""
    d: dict[str, Any] = {
        "uid": team.uid,
        "name": team.name,
        "type": team.type,
        "group": group_to_dict(team.group),
    }
    if team.tab_name:
        d["tab_name"] = team.tab_name
    if team.description:
        d["description"] = team.description
    if team.parent:
        d["parent"] = {"name": team.parent.name, "type": team.parent.type}
    return d


def org_to_dict(org: Org) -> dict[str, Any]:
    """Convert Org to dictionary."""
    d: dict[str, Any] = {
        "uid": org.uid,
        "name": org.name,
        "type": org.type,
        "group": group_to_dict(org.group),
    }
    if org.tab_name:
        d["tab_name"] = org.tab_name
    if org.description:
        d["description"] = org.description
    if org.parent:
        d["parent"] = {"name": org.parent.name, "type": org.parent.type}
    return d


def pillar_to_dict(pillar: Pillar) -> dict[str, Any]:
    """Convert Pillar to dictionary."""
    d: dict[str, Any] = {
        "uid": pillar.uid,
        "name": pillar.name,
        "type": pillar.type,
        "group": group_to_dict(pillar.group),
    }
    if pillar.tab_name:
        d["tab_name"] = pillar.tab_name
    if pillar.description:
        d["description"] = pillar.description
    if pillar.parent:
        d["parent"] = {"name": pillar.parent.name, "type": pillar.parent.type}
    return d


def team_group_to_dict(team_group: TeamGroup) -> dict[str, Any]:
    """Convert TeamGroup to dictionary."""
    d: dict[str, Any] = {
        "uid": team_group.uid,
        "name": team_group.name,
        "type": team_group.type,
        "group": group_to_dict(team_group.group),
    }
    if team_group.tab_name:
        d["tab_name"] = team_group.tab_name
    if team_group.description:
        d["description"] = team_group.description
    if team_group.parent:
        d["parent"] = {"name": team_group.parent.name, "type": team_group.parent.type}
    return d
