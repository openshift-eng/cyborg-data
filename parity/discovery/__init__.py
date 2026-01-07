"""Discovery module for API parity checking."""

from .go_parser import parse_go_interface, GoMethod
from .python_introspector import introspect_python_service, PythonMethod
from .name_mapping import normalize

__all__ = [
    "parse_go_interface",
    "GoMethod",
    "introspect_python_service",
    "PythonMethod",
    "normalize",
]
