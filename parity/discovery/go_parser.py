"""Parse Go interface.go to extract method signatures."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GoMethod:
    """Represents a Go method signature."""

    name: str
    params: list[tuple[str, str]]  # [(param_name, param_type), ...]
    return_type: str


def parse_go_interface(interface_path: Path) -> list[GoMethod]:
    """Parse Go interface.go and extract public methods from ServiceInterface.

    Args:
        interface_path: Path to go/interface.go

    Returns:
        List of GoMethod objects representing the interface methods.
    """
    content = interface_path.read_text()

    # Find the ServiceInterface block
    interface_match = re.search(
        r'type\s+ServiceInterface\s+interface\s*\{([^}]+)\}',
        content,
        re.DOTALL
    )

    if not interface_match:
        raise ValueError("Could not find ServiceInterface in interface.go")

    interface_body = interface_match.group(1)

    methods = []
    method_pattern = re.compile(
        r'^\s*(\w+)\s*\(([^)]*)\)\s*(.+?)\s*$',
        re.MULTILINE
    )

    for match in method_pattern.finditer(interface_body):
        name = match.group(1)
        params_str = match.group(2).strip()
        return_type = match.group(3).strip()

        # Skip comments
        if name.startswith('//'):
            continue

        params = parse_params(params_str)
        methods.append(GoMethod(name=name, params=params, return_type=return_type))

    return methods


def parse_params(params_str: str) -> list[tuple[str, str]]:
    """Parse Go parameter string into list of (name, type) tuples.

    Examples:
        "uid string" -> [("uid", "string")]
        "uid string, teamName string" -> [("uid", "string"), ("teamName", "string")]
        "" -> []
        "ctx context.Context, source DataSource" -> [("ctx", "context.Context"), ("source", "DataSource")]
    """
    if not params_str:
        return []

    params = []
    for param in params_str.split(','):
        param = param.strip()
        if not param:
            continue

        # Split on last space to handle types like "context.Context"
        parts = param.rsplit(' ', 1)
        if len(parts) == 2:
            params.append((parts[0].strip(), parts[1].strip()))
        else:
            # Handle case where type is implied from previous param
            params.append(("", parts[0].strip()))

    return params


def get_return_type_category(return_type: str) -> str:
    """Categorize Go return type for serialization.

    Args:
        return_type: Go return type string like "*Employee" or "[]string"

    Returns:
        Category string like "entity_pointer", "string_list", "bool"
    """
    return_type = return_type.strip()

    if return_type == "bool":
        return "bool"
    if return_type == "error":
        return "error"
    if return_type.startswith("[]string"):
        return "string_list"
    if return_type.startswith("[]"):
        return "entity_list"
    if return_type.startswith("*"):
        return "entity_pointer"
    if return_type == "time.Duration":
        return "duration"
    if return_type == "DataVersion":
        return "data_version"

    return "unknown"
