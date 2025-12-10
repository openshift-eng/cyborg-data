# Examples

## comprehensive/

Full-featured example showing GCS usage, queries, and data source patterns.

```bash
cd comprehensive
go build .
./comprehensive
```

## with-gcs/

GCS-specific example with hot reload.

**Stub mode (no GCS SDK):**
```bash
cd with-gcs
go build .
./with-gcs
```

**Full GCS mode:**
```bash
cd with-gcs
go build -tags gcs .
./with-gcs
```

## Build Tags

| Build | Dependencies | Data Source |
|-------|-------------|-------------|
| `go build .` | stdlib only | Stub (errors on use) |
| `go build -tags gcs .` | GCS SDK | Google Cloud Storage |

## Query API

Both examples use the same query interface:

```go
service := orgdatacore.NewService()
service.LoadFromDataSource(ctx, dataSource)

employee := service.GetEmployeeByUID("jsmith")
teams := service.GetTeamsForSlackID("U123456")
orgs := service.GetUserOrganizations("U123456")
```
