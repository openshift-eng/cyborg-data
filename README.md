# cyborg-data

High-performance organizational data access library with **O(1) lookups** for employee, team, organization, pillar, and team group queries.

Available in **Go** and **Python** with identical APIs.

---

## 🚀 Quick Start

### Go

```bash
cd go
go get github.com/openshift-eng/cyborg-data/go
```

```go
import orgdatacore "github.com/openshift-eng/cyborg-data/go"

service := orgdatacore.NewService()
// Load data from GCS, file, etc.
employee := service.GetEmployeeByUID("user123")
```

👉 **[Full Go Documentation](go/README.md)**

### Python

```bash
cd python
pip install -e .
# or with GCS support:
pip install -e ".[gcs]"
```

```python
from orgdatacore import Service

service = Service()
# Load data from GCS, file, etc.
employee = service.get_employee_by_uid("user123")
```

👉 **[Full Python Documentation](python/README.md)**

---

## 📦 Repository Structure

This is a **multi-language monorepo** containing identical implementations in Go and Python:

```
cyborg-data/
├── go/                          # Go implementation
│   ├── service.go               # Core service
│   ├── types.go                 # Data structures
│   ├── example/                 # Example applications
│   ├── go.mod                   # Go module
│   └── README.md                # Go-specific docs
│
├── python/                      # Python implementation
│   ├── orgdatacore/             # Package source
│   ├── tests/                   # Python tests
│   ├── examples/                # Example applications
│   ├── pyproject.toml           # Python package config
│   └── README.md                # Python-specific docs
│
├── testdata/                    # Shared test fixtures
│   └── test_org_data.json       # Test dataset
│
├── docs/                        # Shared documentation
│   └── PROW_CI.md               # Prow CI integration guide
│
├── .ci-operator.yaml            # OpenShift Prow CI configuration
│
└── Makefile                     # Multi-language build orchestration
```

---

## 🏗️ Architecture

Both implementations share the same architecture:

### Key Principle
**All organizational relationships are pre-computed during indexing.** No expensive tree traversals occur at query time.

### Data Flow
```
Data Source (GCS) → LoadFromDataSource() → In-memory indexes → O(1) queries
```

### Performance Characteristics
- **GetEmployeeByUID**: O(1) direct map lookup
- **GetEmployeeBySlackID**: O(1) index lookup + map lookup
- **GetEmployeeByGitHubID**: O(1) index lookup + map lookup
- **GetTeamsForUID**: O(1) index lookup (no traversal)
- **IsEmployeeInTeam**: O(1) index scan (pre-computed memberships)

---

## 🔧 Building & Testing

### Multi-Language Commands

```bash
# Test both implementations
make test

# Lint both implementations
make lint

# Build both implementations
make build

# Clean all artifacts
make clean
```

### Go-Specific Commands

```bash
cd go

# Run tests
make test

# Run tests with GCS support
make test-with-gcs

# Build examples
make examples

# Run benchmarks
make bench

# Lint code
make lint
```

### Python-Specific Commands

```bash
cd python

# Run tests
pytest

# Run tests with coverage
pytest --cov=orgdatacore

# Lint code
ruff check .

# Format code
ruff format .

# Build package
uv build
```

---

## 📚 API Reference

Both Go and Python implementations provide the same interface:

### Employee Queries
- `GetEmployeeByUID(uid) → Employee`
- `GetEmployeeBySlackID(slackID) → Employee`
- `GetEmployeeByGitHubID(githubID) → Employee`
- `GetManagerForEmployee(uid) → Employee`

### Entity Queries
- `GetTeamByName(teamName) → Team`
- `GetOrgByName(orgName) → Org`
- `GetPillarByName(pillarName) → Pillar`
- `GetTeamGroupByName(teamGroupName) → TeamGroup`

### Membership Queries
- `GetTeamsForUID(uid) → []string`
- `GetTeamsForSlackID(slackID) → []string`
- `GetTeamMembers(teamName) → []Employee`
- `IsEmployeeInTeam(uid, teamName) → bool`
- `IsSlackUserInTeam(slackID, teamName) → bool`

### Organization Queries
- `IsEmployeeInOrg(uid, orgName) → bool`
- `IsSlackUserInOrg(slackID, orgName) → bool`
- `GetUserOrganizations(slackUserID) → []OrgInfo`

### Enumeration
- `GetAllEmployeeUIDs() → []string`
- `GetAllTeamNames() → []string`
- `GetAllOrgNames() → []string`
- `GetAllPillarNames() → []string`
- `GetAllTeamGroupNames() → []string`

---

## 🎯 Use Cases

- **Slack Bots**: Query employee data by Slack ID
- **REST APIs**: Expose organizational data endpoints
- **CLI Tools**: Build command-line utilities for org queries
- **Data Pipelines**: Process organizational hierarchies
- **Access Control**: Validate team/org membership

---

## 🔄 Data Source Support

Both implementations support:

### GCS (Google Cloud Storage)
- **Go**: Requires `-tags gcs` build flag
- **Python**: Install with `pip install -e ".[gcs]"`
- Hot-reload via `Watch()` for automatic updates

### File (Development/Testing)
- Internal testing support
- Fast local development
- Shared test fixtures in `testdata/`

---

## 📖 Data Format

Both implementations consume the same JSON format generated by the upstream Python `orglib` in the cyborg project:

```json
{
  "metadata": { "generated_at": "...", "total_employees": 100 },
  "lookups": {
    "employees": { "uid": { "uid": "...", "full_name": "...", ... } },
    "teams": { "team_name": { ... } },
    "orgs": { "org_name": { ... } },
    "pillars": { "pillar_name": { ... } },
    "team_groups": { "team_group_name": { ... } }
  },
  "indexes": {
    "membership": { ... },
    "slack_id_mappings": { ... },
    "github_id_mappings": { ... }
  }
}
```

---

## 🤝 Contributing

### For Go
See [go/README.md](go/README.md) for Go-specific development guidelines.

### For Python
See [python/README.md](python/README.md) for Python-specific development guidelines.

### API Parity
When adding features, ensure both Go and Python implementations are updated to maintain API parity.

---

## 📄 License

Apache 2.0 - See [LICENSE](LICENSE) for details.

---

## 🔗 Links

- **Repository**: https://github.com/openshift-eng/cyborg-data
- **Go Module**: `github.com/openshift-eng/cyborg-data/go`
- **Python Package**: `orgdatacore` (PyPI)
- **Issues**: https://github.com/openshift-eng/cyborg-data/issues

---

## 🎓 Language-Specific Documentation

- **[Go Documentation](go/README.md)** - Go module usage, build tags, examples
- **[Python Documentation](python/README.md)** - Python package usage, async support, examples
- **[CLAUDE.md](CLAUDE.md)** - AI assistant guidance for both languages
