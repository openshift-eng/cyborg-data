# Python Implementation Guide

## Quick Reference

```bash
cd python
pytest                    # Run all tests
pytest tests/test_employee.py  # Run specific tests
ruff check . && ruff format .  # Lint and format
mypy orgdatacore          # Type check
```

## Extending the API

### Adding a New Query Method

Follow this exact pattern for every new method:

#### Step 1: Implement in Service (`_service.py`)

```python
def get_new_thing_by_param(self, param: str) -> NewThing | None:
    """Get a NewThing by param.

    Args:
        param: The parameter to look up.

    Returns:
        The NewThing if found, None otherwise.
    """
    with self._lock:
        # ALWAYS check for None data first
        if self._data is None or not self._data.lookups.some_map:
            return None

        # Use O(1) lookup - NEVER traverse
        return self._data.lookups.some_map.get(param)
```

#### Step 2: Add Tests (`tests/test_*.py`)

```python
class TestGetNewThingByParam:
    """Tests for new thing lookup by param."""

    @pytest.mark.parametrize("param,expected", [
        ("valid", NewThing(uid="valid", name="Valid Thing")),
        ("nonexistent", None),
        ("", None),
    ])
    def test_get_new_thing_by_param(
        self, service: Service, param: str, expected: NewThing | None
    ):
        """Test new thing lookup by param."""
        result = service.get_new_thing_by_param(param)
        assert result == expected
```

### Design Rules

1. **Thread Safety**: Always use `with self._lock:` for data access
2. **None Checks**: Check `self._data` and the specific collection before accessing
3. **Return Optional**: Return `Type | None` for single entities
4. **Return Lists**: Return `list[Type]` for collections (empty list, not None)
5. **Type Hints**: All parameters and returns must be typed

### Performance Guidelines

**Hot path methods** (called frequently, latency-sensitive):
- MUST use pre-computed indexes for O(1) lookup
- Examples: `get_employee_by_slack_id`, `is_employee_in_team`, `get_teams_for_uid`

**Cold path methods** (infrequent, admin/debug use):
- MAY traverse data if index cost outweighs benefit
- Document the O(n) complexity in docstring
- Examples: `get_employee_by_email`, `get_all_employee_uids`

When adding a new method, consider:
- How often will this be called?
- Is there an existing index that covers this case?
- Would a new index significantly grow the data file?

If traversal is acceptable, document it:
```python
def get_employee_by_email(self, email: str) -> Employee | None:
    """Get an employee by email address.

    Note: O(n) scan - use get_employee_by_uid for hot paths.
    """
```

### Method Categories

| Category | Return Type | None Check Pattern |
|----------|-------------|-------------------|
| Single entity lookup | `Employee \| None` | Return `None` if not found |
| Collection lookup | `list[str]` | Return empty list `[]` |
| Boolean check | `bool` | Return `False` if data unavailable |
| Version/metadata | `DataVersion` | Return default instance |

### Lookup Patterns

**Direct dict lookup** (e.g., get_employee_by_uid):
```python
def get_employee_by_uid(self, uid: str) -> Employee | None:
    with self._lock:
        if self._data is None or not self._data.lookups.employees:
            return None
        return self._data.lookups.employees.get(uid)
```

**Two-step lookup** (e.g., get_employee_by_slack_id):
```python
def get_employee_by_slack_id(self, slack_id: str) -> Employee | None:
    with self._lock:
        if (
            self._data is None
            or not self._data.indexes.slack_id_mappings.slack_uid_to_uid
            or not self._data.lookups.employees
        ):
            return None

        uid = self._data.indexes.slack_id_mappings.slack_uid_to_uid.get(slack_id, "")
        if not uid:
            return None

        return self._data.lookups.employees.get(uid)
```

**Membership iteration** (e.g., get_teams_for_uid):
```python
def get_teams_for_uid(self, uid: str) -> list[str]:
    with self._lock:
        if self._data is None or not self._data.indexes.membership.membership_index:
            return []

        memberships = self._data.indexes.membership.membership_index.get(uid, ())
        return [m.name for m in memberships if m.type == MembershipType.TEAM]
```

## File Organization

| File | Purpose |
|------|---------|
| `_service.py` | `Service` class implementation |
| `_types.py` | Data structures (Employee, Team, etc.) |
| `_exceptions.py` | Custom exceptions |
| `_log.py` | Logging utilities |
| `_gcs.py` | GCS data source (optional) |
| `__init__.py` | Public API exports |

### Test File Mapping

| Entity | Test File |
|--------|-----------|
| Employee queries | `tests/test_employee.py` |
| Team queries | `tests/test_team.py` |
| Org queries | `tests/test_organization.py` |
| Pillar queries | `tests/test_pillar.py` |
| TeamGroup queries | `tests/test_team_group.py` |
| Service lifecycle | `tests/test_service.py` |
| Edge cases | `tests/test_edge_cases.py` |

## Adding a New Entity Type

1. Add dataclass to `_types.py`:
```python
@dataclass(frozen=True, slots=True)
class NewEntity:
    """Represents a new entity in the organizational data."""

    uid: str = ""
    name: str = ""
    # ... fields match JSON structure
```

2. Add to `Lookups` dataclass:
```python
@dataclass(frozen=True, slots=True)
class Lookups:
    # ... existing fields ...
    new_entities: dict[str, NewEntity] = field(default_factory=dict)
```

3. Add parser function in `_service.py`:
```python
def _parse_new_entity(data: dict[str, Any]) -> NewEntity:
    """Parse a NewEntity from a dictionary."""
    return NewEntity(
        uid=data.get("uid", ""),
        name=data.get("name", ""),
    )
```

4. Update `_parse_data()` to include the new entity

5. Add query method following the pattern above

6. Add tests and update `testdata/test_org_data.json`

## Adding a New Index Mapping

For new external ID → UID mappings:

1. Add mapping dataclass to `_types.py`:
```python
@dataclass(frozen=True, slots=True)
class NewIDMappings:
    """Contains New ID to UID mappings."""

    new_id_to_uid: dict[str, str] = field(default_factory=dict)
```

2. Add to `Indexes` dataclass:
```python
@dataclass(frozen=True, slots=True)
class Indexes:
    # ... existing fields ...
    new_id_mappings: NewIDMappings = field(default_factory=NewIDMappings)
```

3. Update `_parse_data()` to parse the new mappings

4. Add lookup method following the two-step pattern

## Type Hints

All code must pass `mypy --strict`:

```python
# Correct: Union with None for optional returns
def get_employee_by_uid(self, uid: str) -> Employee | None:

# Correct: List for collections
def get_all_team_names(self) -> list[str]:

# Correct: Tuple for immutable sequences in dataclasses
@dataclass(frozen=True, slots=True)
class SlackConfig:
    channels: tuple[ChannelInfo, ...] = ()
```

## Dataclass Conventions

Always use frozen, slotted dataclasses:
```python
@dataclass(frozen=True, slots=True)
class Employee:
    uid: str = ""
    full_name: str = ""
    # Default values for all fields
```

- `frozen=True`: Immutability for thread safety
- `slots=True`: Memory efficiency

## Protocol-Based DataSource

DataSource uses Protocol (structural typing):
```python
class DataSource(Protocol):
    def load(self) -> BinaryIO: ...
    def watch(self, callback: Callable[[], Exception | None]) -> Exception | None: ...
    def __str__(self) -> str: ...
```

No inheritance required - just implement the methods.

## Logging

Use the standard library logger:
```python
from ._log import get_logger

logger = get_logger()
logger.info("action completed", extra={"key": value})
logger.error("action failed", extra={"error": str(e)})
```

## Optional Dependencies

GCS support via extras:
```bash
pip install orgdatacore[gcs]
```

Check availability at runtime:
```python
try:
    from google.cloud import storage
    HAS_GCS = True
except ImportError:
    HAS_GCS = False
```

## Test Fixtures

Use pytest fixtures from `conftest.py`:
```python
@pytest.fixture
def service() -> Service:
    """Create a service with test data loaded."""
    # Uses shared testdata/test_org_data.json
    ...
```

## Remember

After implementing in Python:
1. **Implement the same method in Go** (see `go/CLAUDE.md`)
2. Run `make test` from repository root to verify parity
