"""Name mapping between Go PascalCase and Python snake_case.

Uses simple normalization: lowercase and remove underscores.
This avoids needing special cases for acronyms, plurals, etc.
"""


def normalize(name: str) -> str:
    """Normalize a method name for comparison.

    Removes case sensitivity and underscores so that:
    - GetAllEmployeeUIDs -> getallemployeeuids
    - get_all_employee_uids -> getallemployeeuids

    This allows matching without maintaining special cases for
    acronyms (UID, GCS, API) or naming edge cases (GitHub).
    """
    return name.lower().replace("_", "")
