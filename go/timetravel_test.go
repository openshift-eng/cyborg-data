package orgdatacore

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"strconv"
	"testing"
	"time"

	testingsupport "github.com/openshift-eng/cyborg-data/go/internal/testing"
)

// historicalFake adapts the internal fake GCS source into a HistoricalDataSource.
// It lives here (package orgdatacore) because DataVersionRef cannot be referenced
// from internal/testing without an import cycle.
type historicalFake struct {
	*testingsupport.FakeGCSDataSource
}

func (h historicalFake) ListVersions(ctx context.Context) ([]DataVersionRef, error) {
	var refs []DataVersionRef
	for _, blob := range h.Bucket().Versions(h.ObjectPath()) {
		refs = append(refs, DataVersionRef{
			ID:      strconv.FormatInt(blob.Generation, 10),
			Created: blob.Updated,
		})
	}
	return refs, nil
}

func (h historicalFake) LoadVersion(ctx context.Context, ref DataVersionRef) (io.ReadCloser, error) {
	gen, err := strconv.ParseInt(ref.ID, 10, 64)
	if err != nil {
		return nil, err
	}
	blob, ok := h.Bucket().GetGenerationBlob(h.ObjectPath(), gen)
	if !ok {
		return nil, fmt.Errorf("generation %d not found", gen)
	}
	return io.NopCloser(bytes.NewReader(blob.Content)), nil
}

// versionJSON builds a minimal valid index carrying a distinguishable
// data_version and a single employee uid.
func versionJSON(dataVersion, empUID string) []byte {
	return fmt.Appendf(nil, `{
		"metadata": {"generated_at": %q, "data_version": %q},
		"lookups": {
			"employees": {%q: {"uid": %q, "full_name": "User", "email": "u@test.com", "job_title": "Dev"}},
			"teams": {}, "orgs": {}
		},
		"indexes": {
			"membership": {"membership_index": {%q: []}, "relationship_index": {}},
			"slack_id_mappings": {"slack_uid_to_uid": {}},
			"github_id_mappings": {"github_id_to_uid": {}}
		}
	}`, dataVersion, dataVersion, empUID, empUID, empUID)
}

// newHistoryFixture builds a historical source with three versions at known
// times: v1 (t0), v2 (t0+24h), v3 (t0+48h).
func newHistoryFixture(t0 time.Time) historicalFake {
	src := testingsupport.NewFakeGCSDataSourceAt("bucket", "org.json", versionJSON("v1", "emp1"), t0)
	if err := src.AddVersionAt(versionJSON("v2", "emp2"), t0.Add(24*time.Hour)); err != nil {
		panic(err)
	}
	if err := src.AddVersionAt(versionJSON("v3", "emp3"), t0.Add(48*time.Hour)); err != nil {
		panic(err)
	}
	return historicalFake{src}
}

func TestAsOfResolvesVersionLiveAtTime(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := newHistoryFixture(t0)
	svc := NewService()
	ctx := context.Background()

	tests := []struct {
		name        string
		at          time.Time
		wantVersion string
		wantEmp     string
	}{
		{"exactly at v1", t0, "v1", "emp1"},
		{"between v1 and v2 resolves v1", t0.Add(12 * time.Hour), "v1", "emp1"},
		{"exactly at v2", t0.Add(24 * time.Hour), "v2", "emp2"},
		{"between v2 and v3 resolves v2", t0.Add(36 * time.Hour), "v2", "emp2"},
		{"after v3 resolves v3", t0.Add(100 * time.Hour), "v3", "emp3"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			view, err := svc.AsOf(ctx, src, tt.at)
			if err != nil {
				t.Fatalf("AsOf(%v) error: %v", tt.at, err)
			}
			if got := view.GetDataVersion(); got != tt.wantVersion {
				t.Errorf("GetDataVersion() = %q, want %q", got, tt.wantVersion)
			}
			if emp := view.GetEmployeeByUID(tt.wantEmp); emp == nil {
				t.Errorf("expected employee %q present in version %s", tt.wantEmp, tt.wantVersion)
			}
		})
	}
}

func TestAsOfBeforeEarliestReturnsErrVersionNotAvailable(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := newHistoryFixture(t0)
	svc := NewService()

	_, err := svc.AsOf(context.Background(), src, t0.Add(-time.Hour))
	if !errors.Is(err, ErrVersionNotAvailable) {
		t.Fatalf("expected ErrVersionNotAvailable, got %v", err)
	}
}

func TestAsOfNonHistoricalSourceReturnsNotSupported(t *testing.T) {
	// The bare fake does not implement HistoricalDataSource.
	src := testingsupport.NewFakeGCSDataSource("bucket", "org.json", versionJSON("v1", "emp1"))
	svc := NewService()

	_, err := svc.AsOf(context.Background(), src, time.Now())
	if !errors.Is(err, ErrTimeTravelNotSupported) {
		t.Fatalf("expected ErrTimeTravelNotSupported, got %v", err)
	}

	_, err = svc.ListVersions(context.Background(), src)
	if !errors.Is(err, ErrTimeTravelNotSupported) {
		t.Fatalf("ListVersions: expected ErrTimeTravelNotSupported, got %v", err)
	}
}

func TestListVersionsSortedOldestFirst(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := newHistoryFixture(t0)
	svc := NewService()

	refs, err := svc.ListVersions(context.Background(), src)
	if err != nil {
		t.Fatalf("ListVersions error: %v", err)
	}
	if len(refs) != 3 {
		t.Fatalf("expected 3 versions, got %d", len(refs))
	}
	for i := 1; i < len(refs); i++ {
		if refs[i].Created.Before(refs[i-1].Created) {
			t.Errorf("versions not sorted oldest-first: %v before %v", refs[i].Created, refs[i-1].Created)
		}
	}
}

func TestAsOfCachesResolvedSnapshot(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := newHistoryFixture(t0)
	svc := NewService()
	ctx := context.Background()

	first, err := svc.AsOf(ctx, src, t0.Add(12*time.Hour))
	if err != nil {
		t.Fatalf("first AsOf error: %v", err)
	}
	second, err := svc.AsOf(ctx, src, t0.Add(6*time.Hour)) // different time, same version (v1)
	if err != nil {
		t.Fatalf("second AsOf error: %v", err)
	}
	if first != second {
		t.Error("expected AsOf to return the cached snapshot for the same resolved version")
	}
}

func TestAsOfCacheDisabled(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := newHistoryFixture(t0)
	svc := NewService(WithHistoryCacheSize(0))
	ctx := context.Background()

	first, _ := svc.AsOf(ctx, src, t0)
	second, _ := svc.AsOf(ctx, src, t0)
	if first == second {
		t.Error("expected distinct snapshots when caching is disabled")
	}
}

func TestAsOfThroughRedactingSource(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := newHistoryFixture(t0)
	redacting := NewRedactingDataSource(src, PIIModeRedacted)
	svc := NewService()

	view, err := svc.AsOf(context.Background(), redacting, t0)
	if err != nil {
		t.Fatalf("AsOf through redacting source error: %v", err)
	}
	emp := view.GetEmployeeByUID("emp1")
	if emp == nil {
		t.Fatal("expected employee present in redacted historical view")
	}
	if emp.FullName != "[REDACTED]" {
		t.Errorf("expected redacted full name, got %q", emp.FullName)
	}
}

func TestAsOfThroughRedactingNonHistoricalSource(t *testing.T) {
	// Redacting wraps a non-historical source: time travel must not be claimed.
	bare := testingsupport.NewFakeGCSDataSource("bucket", "org.json", versionJSON("v1", "emp1"))
	redacting := NewRedactingDataSource(bare, PIIModeRedacted)
	svc := NewService()

	_, err := svc.AsOf(context.Background(), redacting, time.Now())
	if !errors.Is(err, ErrTimeTravelNotSupported) {
		t.Fatalf("expected ErrTimeTravelNotSupported, got %v", err)
	}
}
