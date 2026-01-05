"""Discovery module for API parity checking."""

from .go_parser import parse_go_interface, GoMethod
from .python_introspector import introspect_python_service, PythonMethod
from .name_mapping import go_to_python, python_to_go

__all__ = [
    "parse_go_interface",
    "GoMethod",
    "introspect_python_service",
    "PythonMethod",
    "go_to_python",
    "python_to_go",
]
