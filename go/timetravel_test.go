package orgdatacore

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"reflect"
	"strconv"
	"strings"
	"testing"
	"time"

	testingsupport "github.com/openshift-eng/cyborg-data/go/internal/testing"
)

// countingHistorical counts ListVersions calls, to verify the version-list cache.
type countingHistorical struct {
	historicalFake
	listCalls *int
}

func (c countingHistorical) ListVersions(ctx context.Context) ([]DataVersionRef, error) {
	*c.listCalls++
	return c.historicalFake.ListVersions(ctx)
}

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

// prunedHistorical simulates a version that was listed but pruned before read.
type prunedHistorical struct {
	historicalFake
}

func (p prunedHistorical) LoadVersion(ctx context.Context, ref DataVersionRef) (io.ReadCloser, error) {
	return nil, fmt.Errorf("%w: generation %s pruned", ErrVersionNotAvailable, ref.ID)
}

func TestAsOfPropagatesPrunedVersion(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := prunedHistorical{newHistoryFixture(t0)}
	svc := NewService()

	_, err := svc.AsOf(context.Background(), src, t0.Add(12*time.Hour))
	if !errors.Is(err, ErrVersionNotAvailable) {
		t.Fatalf("expected ErrVersionNotAvailable for a pruned generation, got %v", err)
	}
}

func TestAsOfCacheKeyIsolatesWrappedSources(t *testing.T) {
	// A snapshot resolved through a raw source must never be served to a
	// redacting wrapper over the same source (shared generation ID) -- that
	// would leak PII.
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	raw := newHistoryFixture(t0)
	svc := NewService()
	ctx := context.Background()

	rawView, err := svc.AsOf(ctx, raw, t0)
	if err != nil {
		t.Fatalf("raw AsOf error: %v", err)
	}
	if got := rawView.GetEmployeeByUID("emp1").FullName; got != "User" {
		t.Fatalf("raw view full name = %q, want %q", got, "User")
	}

	redacting := NewRedactingDataSource(raw, PIIModeRedacted)
	redView, err := svc.AsOf(ctx, redacting, t0)
	if err != nil {
		t.Fatalf("redacting AsOf error: %v", err)
	}
	if got := redView.GetEmployeeByUID("emp1").FullName; got != "[REDACTED]" {
		t.Errorf("PII leak: redacting view full name = %q, want %q (cache served the raw snapshot?)", got, "[REDACTED]")
	}
}

func TestAsOfCachesVersionListing(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	calls := 0
	src := countingHistorical{historicalFake: newHistoryFixture(t0), listCalls: &calls}
	svc := NewService()
	ctx := context.Background()

	if _, err := svc.AsOf(ctx, src, t0.Add(12*time.Hour)); err != nil {
		t.Fatalf("AsOf error: %v", err)
	}
	if _, err := svc.AsOf(ctx, src, t0.Add(36*time.Hour)); err != nil {
		t.Fatalf("AsOf error: %v", err)
	}
	if calls != 1 {
		t.Errorf("expected version listing to be fetched once (cached), got %d calls", calls)
	}
}

func TestAnonymizeLoadVersionPreservesLiveState(t *testing.T) {
	// Time-traveling through an anonymizing wrapper must not disturb the live
	// nonce tables that the live data depends on.
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	base := newHistoryFixture(t0)
	anon := NewAnonymizingDataSource(base, PIIModeAnonymized)
	svc := NewService()
	ctx := context.Background()

	if err := svc.LoadFromDataSource(ctx, anon); err != nil {
		t.Fatalf("live load error: %v", err)
	}
	before := anon.UIDToNonceMap()
	if len(before) == 0 {
		t.Fatal("expected a live nonce map after load")
	}

	if _, err := svc.AsOf(ctx, anon, t0); err != nil {
		t.Fatalf("historical AsOf error: %v", err)
	}
	after := anon.UIDToNonceMap()
	if !reflect.DeepEqual(before, after) {
		t.Errorf("historical load disturbed live nonce tables:\n before=%v\n after =%v", before, after)
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

// fixedHistorical returns a caller-owned, unsorted version slice verbatim, to
// verify ListVersions sorts a copy rather than mutating the source's slice.
type fixedHistorical struct {
	historicalFake
	refs []DataVersionRef
}

func (f fixedHistorical) ListVersions(ctx context.Context) ([]DataVersionRef, error) {
	return f.refs, nil
}

func TestListVersionsDoesNotMutateSourceSlice(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	// Caller-owned slice in newest-first order; ListVersions must not reorder it.
	own := []DataVersionRef{
		{ID: "2", Created: t0.Add(time.Hour)},
		{ID: "1", Created: t0},
	}
	src := fixedHistorical{historicalFake: newHistoryFixture(t0), refs: own}
	svc := NewService()

	out, err := svc.ListVersions(context.Background(), src)
	if err != nil {
		t.Fatalf("ListVersions error: %v", err)
	}
	if out[0].ID != "1" || out[1].ID != "2" {
		t.Errorf("returned listing not sorted oldest-first: %+v", out)
	}
	if own[0].ID != "2" || own[1].ID != "1" {
		t.Errorf("source-owned slice was mutated by sort: %+v", own)
	}
}

func TestResolveVersionStableTieBreak(t *testing.T) {
	// Versions sharing an identical Created time must resolve deterministically;
	// a stable sort preserves the source's input order for the tie.
	same := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	refs := []DataVersionRef{{ID: "first", Created: same}, {ID: "second", Created: same}}
	sortVersionsByCreated(refs)
	if refs[0].ID != "first" || refs[1].ID != "second" {
		t.Errorf("stable sort did not preserve input order for equal times: %+v", refs)
	}
	// resolveVersion keeps the first at-or-before t among equal times (strict
	// After tie-break, matching Python's strict > tie-break), so with the stable
	// input order the result is deterministically the first element.
	ref, err := resolveVersion(refs, same)
	if err != nil {
		t.Fatalf("resolveVersion error: %v", err)
	}
	if ref.ID != "first" {
		t.Errorf("resolveVersion tie-break = %q, want deterministic %q", ref.ID, "first")
	}
}

func TestAsOfViewIsReadOnly(t *testing.T) {
	// A historical view is shared across cache hits, so its mutating methods
	// must refuse to run rather than corrupt the cached snapshot.
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	src := newHistoryFixture(t0)
	svc := NewService()
	ctx := context.Background()

	view, err := svc.AsOf(ctx, src, t0)
	if err != nil {
		t.Fatalf("AsOf error: %v", err)
	}
	concrete, ok := view.(*Service)
	if !ok {
		t.Fatalf("AsOf returned %T, want *Service", view)
	}

	if err := concrete.LoadFromDataSource(ctx, src); !errors.Is(err, ErrReadOnlyView) {
		t.Errorf("LoadFromDataSource on view: got %v, want ErrReadOnlyView", err)
	}
	if err := concrete.StartDataSourceWatcher(ctx, src); !errors.Is(err, ErrReadOnlyView) {
		t.Errorf("StartDataSourceWatcher on view: got %v, want ErrReadOnlyView", err)
	}

	// The snapshot must be untouched by the refused mutations.
	if got := view.GetDataVersion(); got != "v1" {
		t.Errorf("view version changed to %q after refused mutation, want v1", got)
	}
}

// loadErrHistorical returns an already-wrapped *LoadError from ListVersions, to
// verify AsOf/ListVersions do not re-wrap it into a doubly-nested message.
type loadErrHistorical struct {
	historicalFake
	err error
}

func (l loadErrHistorical) ListVersions(ctx context.Context) ([]DataVersionRef, error) {
	return nil, l.err
}

func TestListVersionsDoesNotDoubleWrapLoadError(t *testing.T) {
	t0 := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	inner := NewLoadError("gs://bucket/org.json", errors.New("failed to list object versions"))
	src := loadErrHistorical{historicalFake: newHistoryFixture(t0), err: inner}
	svc := NewService()

	_, err := svc.ListVersions(context.Background(), src)
	if err == nil {
		t.Fatal("expected an error")
	}
	// The source already wrapped in a LoadError; it must be passed through, not
	// nested inside a second "failed to load ...:" prefix.
	var le *LoadError
	if !errors.As(err, &le) {
		t.Fatalf("expected a *LoadError, got %T: %v", err, err)
	}
	if le.Err != inner.Err {
		t.Errorf("error was re-wrapped: got %v, want the original inner error %v", le.Err, inner.Err)
	}
	if strings.Count(err.Error(), "failed to load from") > 1 {
		t.Errorf("doubly-nested load error message: %q", err.Error())
	}
}
