# orgdatacore - Python

Python port of the Go orgdatacore library for organizational data management.

This library provides thread-safe access to organizational data including employees, teams, organizations, pillars, and team groups.

## Installation

```bash
# Install from source
pip install -e .

# With GCS support (recommended for production)
pip install -e ".[gcs]"

# With development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Using GCS (Recommended for Production)

```python
from orgdatacore import Service, GCSConfig
from orgdatacore.datasources import GCSDataSourceWithSDK
from datetime import timedelta

# Configure GCS data source
config = GCSConfig(
    bucket="your-bucket",
    object_path="path/to/org_data.json",
    project_id="your-project",
    check_interval=timedelta(minutes=5),
)
source = GCSDataSourceWithSDK(config)

# Create service and load data
service = Service()
service.load_from_data_source(source)

# Query employees
employee = service.get_employee_by_uid("jsmith")
if employee:
    print(f"Found: {employee.full_name}")
```

### Using a Custom DataSource (S3, Azure, etc.)

The library supports pluggable data sources. Implement the `DataSource` interface for your storage backend:

```python
from orgdatacore import Service
from orgdatacore.interface import DataSource
from typing import BinaryIO, Callable, Optional
from io import BytesIO

class S3DataSource(DataSource):
    """Example custom DataSource for AWS S3."""
    
    def __init__(self, bucket: str, key: str):
        self.bucket = bucket
        self.key = key
    
    def load(self) -> BinaryIO:
        import boto3
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=self.bucket, Key=self.key)
        return BytesIO(response['Body'].read())
    
    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        # Implement watching logic (polling, S3 events, etc.)
        return None
    
    def __str__(self) -> str:
        return f"s3://{self.bucket}/{self.key}"

# Use your custom data source
service = Service()
source = S3DataSource("my-org-bucket", "data/org_data.json")
service.load_from_data_source(source)
```

## API Reference

### Service

The main class providing access to organizational data.

#### Core Data Access

- `get_employee_by_uid(uid: str) -> Employee | None`
- `get_employee_by_slack_id(slack_id: str) -> Employee | None`
- `get_employee_by_github_id(github_id: str) -> Employee | None`
- `get_manager_for_employee(uid: str) -> Employee | None`
- `get_team_by_name(team_name: str) -> Team | None`
- `get_org_by_name(org_name: str) -> Org | None`
- `get_pillar_by_name(pillar_name: str) -> Pillar | None`
- `get_team_group_by_name(team_group_name: str) -> TeamGroup | None`

#### Membership Queries

- `get_teams_for_uid(uid: str) -> list[str]`
- `get_teams_for_slack_id(slack_id: str) -> list[str]`
- `get_team_members(team_name: str) -> list[Employee]`
- `is_employee_in_team(uid: str, team_name: str) -> bool`
- `is_slack_user_in_team(slack_id: str, team_name: str) -> bool`

#### Organization Queries

- `is_employee_in_org(uid: str, org_name: str) -> bool`
- `is_slack_user_in_org(slack_id: str, org_name: str) -> bool`
- `get_user_organizations(slack_user_id: str) -> list[OrgInfo]`

#### Data Management

- `get_version() -> DataVersion`
- `load_from_data_source(source: DataSource) -> None`
- `start_data_source_watcher(source: DataSource) -> None`

#### Enumeration

- `get_all_employee_uids() -> list[str]`
- `get_all_team_names() -> list[str]`
- `get_all_org_names() -> list[str]`
- `get_all_pillar_names() -> list[str]`
- `get_all_team_group_names() -> list[str]`

### DataSource Interface

Implement this interface for custom storage backends:

```python
from orgdatacore.interface import DataSource
from typing import BinaryIO, Callable, Optional

class MyDataSource(DataSource):
    def load(self) -> BinaryIO:
        """Return a file-like object containing JSON data."""
        ...
    
    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        """Start watching for changes, call callback when data updates."""
        ...
    
    def __str__(self) -> str:
        """Return a description of this data source."""
        ...
```

### Data Sources

#### GCSDataSource / GCSDataSourceWithSDK

For production use with Google Cloud Storage (requires `google-cloud-storage`):

```python
from orgdatacore import GCSConfig
from orgdatacore.datasources import GCSDataSourceWithSDK
from datetime import timedelta

config = GCSConfig(
    bucket="your-bucket",
    object_path="path/to/data.json",
    project_id="your-project",
    check_interval=timedelta(minutes=5),
)
source = GCSDataSourceWithSDK(config)
```

## Data Source Policy

**IMPORTANT**: File-based data sources have been removed from the public API for security reasons.

For production deployments:
- Use `GCSDataSourceWithSDK` with proper access controls, or
- Implement a custom `DataSource` for your storage backend (S3, Azure, etc.)

File-based data sources are only available internally for testing purposes and are not part of the public API.

## Thread Safety

The `Service` class is thread-safe. All read operations can be performed concurrently, and data reloading is atomic.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=orgdatacore --cov-report=html
```

### Type Checking

```bash
mypy orgdatacore
```

### Code Formatting

```bash
black orgdatacore tests
isort orgdatacore tests
```

## Examples

Run the GCS demo with real data:

```bash
# Make sure you're logged in
gcloud auth application-default login

# Install GCS support
pip install -e ".[gcs]"

# Run the demo
python examples/gcs_demo.py
```

## License

Apache-2.0
