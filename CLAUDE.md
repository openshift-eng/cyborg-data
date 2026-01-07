# CLAUDE.md

## Project Overview

`cyborg-data` (`orgdatacore`) is a multi-language library for high-performance organizational data access, available in **Go** and **Python**. It provides O(1) lookups for employee, team, organization, pillar, and team group queries through pre-computed indexes.

**Key Principle**: All organizational relationships are pre-computed during indexing. No tree traversals at query time.

## Repository Structure

```
├── go/           # Go implementation (see go/CLAUDE.md)
├── python/       # Python implementation (see python/CLAUDE.md)
├── testdata/     # Shared test fixtures
└── Makefile      # Multi-language orchestration
```

## API Parity Rules

**CRITICAL**: Go and Python implementations MUST maintain API parity. When adding or modifying any API method:

### Parity Checklist

1. **Implement in both languages** - Every public method must exist in both
2. **Match semantics exactly** - Same parameters, same return behavior, same edge cases
3. **Port tests to both** - Test coverage must be equivalent
4. **Run both test suites** - `make test` from root (runs Go and Python)

### Naming Convention Mapping

| Go (PascalCase) | Python (snake_case) |
|-----------------|---------------------|
| `GetEmployeeByUID(uid)` | `get_employee_by_uid(uid)` |
| `IsEmployeeInTeam(uid, team)` | `is_employee_in_team(uid, team)` |
| `LoadFromDataSource(ctx, src)` | `load_from_data_source(source)` |

### When Adding a New Method

```bash
# 1. Implement in Go (see go/CLAUDE.md for patterns)
# 2. Implement in Python (see python/CLAUDE.md for patterns)
# 3. Run parity verification
make test
```

## Automated Parity Check

The `parity/` directory contains an automated tool that verifies Go and Python implementations match.

### How It Works

1. **Discovery**: Parses Go's `ServiceInterface` and introspects Python's `Service` class
2. **Name Matching**: Normalizes names (lowercase, remove underscores) to match across languages
3. **Execution**: Runs both implementations with identical test inputs
4. **Comparison**: Verifies outputs match exactly

### Running the Parity Check

```bash
make validate-parity
```

### Naming Convention

Methods are matched by normalizing names - **case and underscores are ignored**:

| Go | Python | Normalized |
|----|--------|------------|
| `GetEmployeeByUID` | `get_employee_by_uid` | `getemployeebyuid` |
| `GetAllEmployeeUIDs` | `get_all_employee_uids` | `getallemployeeuids` |
| `IsSlackUserInTeam` | `is_slack_user_in_team` | `isslackuserinteam` |

This means you don't need to worry about acronym casing (UID vs Uid) - just follow standard conventions for each language.

### Excluded Methods

Some methods are excluded from parity comparison (defined in `parity/discovery/python_introspector.py`):

```python
EXCLUDED_METHODS = {
    # Lifecycle (exist in both, not automatically testable)
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
```

If you add a language-specific method, add it to `EXCLUDED_METHODS` to prevent false failures.

### What the Tool Catches

- Methods in Go but missing in Python
- Methods in Python but missing in Go (unless excluded)
- Different return values for the same inputs
- Different error behavior

## Build Commands

```bash
# From repository root
make test        # Test both Go and Python
make lint        # Lint both implementations
make go-test     # Test Go only
make python-test # Test Python only
```

## Language-Specific Documentation

For implementation details and extension patterns:
- **Go**: See `go/CLAUDE.md`
- **Python**: See `python/CLAUDE.md`

## Architecture (Both Languages)

### Data Flow
```
DataSource (GCS) → Service.LoadFromDataSource() → In-memory indexes
                                                        ↓
                              Queries use O(1) pre-computed lookups
```

### Core Types (equivalent in both)
- `Service` - Main entry point with thread-safe access
- `Employee`, `Team`, `Org`, `Pillar`, `TeamGroup` - Entity types
- `DataSource` - Interface/Protocol for data loading

### Indexes (consumed, not computed)
- `MembershipIndex[uid]` → teams/orgs the user belongs to
- `SlackUIDToUID[slackID]` → employee UID
- `GitHubIDToUID[githubID]` → employee UID
- `RelationshipIndex[category][name]` → ancestry hierarchy

**Note**: Indexes are generated upstream. This library only consumes them.

## Test Data

Both implementations use shared test fixtures:
- `testdata/test_org_data.json` - Minimal test dataset

## Dependencies Policy

- **Go**: Standard library only (default), GCS via `-tags gcs`
- **Python**: Minimal deps, GCS via `pip install orgdatacore[gcs]`

Avoid adding required dependencies. Optional features use build tags (Go) or extras (Python).
