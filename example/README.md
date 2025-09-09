# cyborg-data Examples

This directory contains examples demonstrating different usage patterns of the cyborg-data library.

## Examples

### `file-only/` - Lightweight File-Based Usage
**No external dependencies required**

**Build & Run:**
```bash
cd file-only
go build .
./file-only
```

### `with-gcs/` - Google Cloud Storage Integration
**Full functionality requires GCS SDK and build tags**

**Build & Run (Stub Mode - Always Works):**
```bash
cd with-gcs
go build .              # Shows warning, demonstrates API
./with-gcs
```

**Build & Run (Full GCS Mode):**
```bash
go get cloud.google.com/go/storage
cd with-gcs
go build -tags gcs .    # Real GCS implementation
./with-gcs
```

### `comprehensive/` - Full-Featured Demo
Shows both file and GCS usage patterns in a single example with automatic feature detection and advanced queries.

**Build & Run:**
```bash
cd comprehensive
go build .
./comprehensive
```

---

## Key Differences

| Feature | file-only/ | with-gcs/ |
|---------|-----------|-----------|
| **Dependencies** | None (stdlib only) | GCS SDK (~50+ packages) |
| **Build Command** | `go build .` | `go build -tags gcs .` |
| **Data Source** | Local files | Google Cloud Storage |
| **Hot Reload** | File system polling | GCS metadata polling |
| **Authentication** | Not needed | Service account or ADC |
| **Binary Size** | Smaller | Larger (includes GCS SDK) |

## Architecture Benefits

The build tag approach provides:

1. **Flexibility**: Teams choose their deployment model
2. **Lightweight Default**: No cloud dependencies unless needed
3. **Pluggable Design**: Easy to add other data sources (HTTP, databases, etc.)
4. **Production Ready**: Both patterns support hot reload and structured logging

## Integration Examples

Both examples show identical query APIs:

```go
// Same code works with any data source
service := orgdatacore.NewService()
service.LoadFromDataSource(ctx, dataSource) // File or GCS

// Identical queries regardless of source
employee := service.GetEmployeeByUID("jsmith")
teams := service.GetTeamsForSlackID("U123456")
orgs := service.GetUserOrganizations("U123456")
```

This demonstrates the power of the `DataSource` interface abstraction.
