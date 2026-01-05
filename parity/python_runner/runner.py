#!/usr/bin/env python3
"""API Parity Test Runner for Python implementation.

Accepts method configuration via stdin and outputs JSON results.
"""

import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))

from orgdatacore import Service  # noqa: E402
from orgdatacore._internal.testing import FileDataSource  # noqa: E402


def main() -> None:
    """Read config from stdin, run tests, output results."""
    config = json.load(sys.stdin)
    svc = load_service(config["test_data_path"])

    results = []
    for method_spec in config["methods"]:
        python_name = method_spec["python_name"]
        for tc in method_spec["test_cases"]:
            results.append(run_test_case(svc, python_name, tc))

    json.dump(results, sys.stdout, indent=2, default=json_serializer)
    print()


def load_service(test_data_path: str) -> Service:
    """Load service with test data."""
    svc = Service()
    source = FileDataSource(test_data_path)
    svc.load_from_data_source(source)
    return svc


def run_test_case(svc: Service, python_name: str, tc: dict[str, Any]) -> dict[str, Any]:
    """Run a single test case."""
    result: dict[str, Any] = {
        "method_python_name": python_name,
        "case_name": tc["name"],
    }

    method = getattr(svc, python_name, None)
    if method is None:
        result["error"] = f"method {python_name} not found"
        result["output"] = None
        return result

    inputs = tc.get("inputs", {})

    try:
        output = method(**inputs)
        result["output"] = serialize_output(output)
    except TypeError:
        try:
            output = method(*list(inputs.values()))
            result["output"] = serialize_output(output)
        except Exception as e2:
            result["error"] = str(e2)
            result["output"] = None
    except Exception as e:
        result["error"] = str(e)
        result["output"] = None

    return result


def serialize_output(output: Any) -> Any:
    """Serialize output for comparison with Go."""
    if output is None:
        return None
    if isinstance(output, bool):
        return output
    if isinstance(output, str):
        return output
    if isinstance(output, (list, tuple)) and all(isinstance(x, str) for x in output):
        return sorted(output)
    if isinstance(output, (list, tuple)) and output and is_dataclass(output[0]):
        return serialize_entity_list(list(output))
    if is_dataclass(output) and not isinstance(output, type):
        return serialize_entity(output)
    if isinstance(output, dict):
        return output
    return output


def serialize_entity(entity: Any) -> dict[str, Any]:
    """Serialize a dataclass entity to match Go output format."""
    entity_type = type(entity).__name__

    if entity_type == "Employee":
        return {
            "uid": entity.uid,
            "full_name": entity.full_name,
            "email": entity.email,
        }
    elif entity_type == "Team":
        return {
            "uid": entity.uid,
            "name": entity.name,
            "description": entity.description,
        }
    elif entity_type == "Org":
        return {
            "uid": entity.uid,
            "name": entity.name,
            "description": entity.description,
        }
    elif entity_type == "Pillar":
        return {
            "uid": entity.uid,
            "name": entity.name,
            "description": entity.description,
        }
    elif entity_type == "TeamGroup":
        return {
            "uid": entity.uid,
            "name": entity.name,
            "description": entity.description,
        }
    elif entity_type == "Component":
        return {
            "name": entity.name,
            "description": entity.description,
        }
    elif entity_type == "HierarchyPathEntry":
        return {
            "name": entity.name,
            "type": entity.type,
        }
    elif entity_type == "HierarchyNode":
        return serialize_hierarchy_node(entity)
    elif entity_type == "OrgInfo":
        return {
            "name": entity.name,
            "type": entity.type,
        }
    elif entity_type == "JiraOwnerInfo":
        return {
            "name": entity.name,
            "type": entity.type,
        }
    elif entity_type == "JiraOwnership":
        return {
            "project": entity.project,
            "component": entity.component,
        }
    else:
        # Generic dataclass serialization
        return asdict(entity)


def serialize_entity_list(entities: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list of entities and sort for deterministic comparison."""
    if not entities:
        return []

    result = [serialize_entity(e) for e in entities]
    entity_type = type(entities[0]).__name__

    if entity_type == "Employee":
        result.sort(key=lambda x: x.get("uid", ""))
    elif entity_type in ("Team", "Org", "Pillar", "TeamGroup", "Component", "OrgInfo", "JiraOwnerInfo"):
        result.sort(key=lambda x: x.get("name", ""))
    elif entity_type == "JiraOwnership":
        result.sort(key=lambda x: (x.get("project", ""), x.get("component", "")))
    elif entity_type == "HierarchyPathEntry":
        pass  # Order matters for hierarchy paths
    elif result and "uid" in result[0]:
        result.sort(key=lambda x: x.get("uid", ""))
    elif result and "name" in result[0]:
        result.sort(key=lambda x: x.get("name", ""))

    return result


def serialize_hierarchy_node(node: Any) -> dict[str, Any]:
    """Serialize hierarchy node recursively."""
    children = [serialize_hierarchy_node(c) for c in (node.children or [])]
    children.sort(key=lambda x: x.get("name", ""))
    return {"name": node.name, "type": node.type, "children": children}


def json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for dataclasses."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


if __name__ == "__main__":
    main()
