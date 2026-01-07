"""Introspect Python Service class to extract method signatures."""

import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_type_hints


@dataclass
class PythonMethod:
    """Represents a Python method signature."""

    name: str
    params: list[tuple[str, Any]]  # [(param_name, param_type), ...]
    return_type: Any


# Methods excluded from parity comparison.
# Two categories:
# 1. Lifecycle methods - exist in both languages but can't be tested automatically
# 2. Language-specific methods - intentionally only in one language
EXCLUDED_METHODS = {
    # Lifecycle (exist in both, not testable)
    "load_from_data_source",
    "start_data_source_watcher",
    "stop_watcher",
    "get_version",
    "get_data_age",
    "is_data_stale",
    # Python-only (intentional, not a parity issue)
    "is_healthy",
    "is_ready",
    "initialize",
}


def introspect_python_service(python_root: Path | None = None) -> list[PythonMethod]:
    """Introspect the Python Service class for public methods.

    Args:
        python_root: Path to python/ directory. If None, tries to find it.

    Returns:
        List of PythonMethod objects representing public methods.
    """
    if python_root:
        sys.path.insert(0, str(python_root))

    from orgdatacore import Service

    methods = []
    for name in dir(Service):
        if name.startswith('_'):
            continue

        attr = getattr(Service, name)
        if not callable(attr):
            continue

        if isinstance(inspect.getattr_static(Service, name), (classmethod, staticmethod)):
            continue

        try:
            sig = inspect.signature(attr)
        except (ValueError, TypeError):
            continue

        try:
            hints = get_type_hints(attr)
        except Exception:
            hints = {}

        params = []
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            params.append((param_name, hints.get(param_name, Any)))

        return_type = hints.get('return', Any)

        methods.append(PythonMethod(
            name=name,
            params=params,
            return_type=return_type
        ))

    return methods


def get_return_type_category(return_type: Any) -> str:
    """Categorize Python return type for serialization.

    Args:
        return_type: Python type annotation

    Returns:
        Category string like "entity_pointer", "string_list", "bool"
    """
    if return_type is None:
        return "none"

    type_str = str(return_type)

    if return_type is bool or type_str == "<class 'bool'>":
        return "bool"
    if "list[str]" in type_str.lower():
        return "string_list"
    if "list[" in type_str.lower():
        return "entity_list"
    if "| None" in type_str or "None |" in type_str:
        return "entity_pointer"
    if "timedelta" in type_str:
        return "duration"
    if "DataVersion" in type_str:
        return "data_version"

    return "unknown"
