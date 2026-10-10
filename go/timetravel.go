package orgdatacore

import (
	"context"
	"fmt"
	"time"
)

// ListVersions returns all retained versions of the index exposed by source,
// sorted oldest-first by creation time. The source must implement
// HistoricalDataSource; otherwise ErrTimeTravelNotSupported is returned.
//
// Results are cached per source for a short TTL (see WithVersionsCacheTTL).
func (s *Service) ListVersions(ctx context.Context, source DataSource) ([]DataVersionRef, error) {
	hist, ok := source.(HistoricalDataSource)
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrTimeTravelNotSupported, source.String())
	}
	refs, err := s.listVersionsCached(ctx, hist, source.String())
	if err != nil {
		return nil, NewLoadError(source.String(), err)
	}
	// Return a copy so callers can't mutate the cached slice.
	out := make([]DataVersionRef, len(refs))
	copy(out, refs)
	return out, nil
}

// listVersionsCached returns the sorted version listing for key, reusing a
// cached listing within versionsTTL. The returned slice is the cached one and
// must be treated as read-only by callers.
func (s *Service) listVersionsCached(ctx context.Context, hist HistoricalDataSource, key string) ([]DataVersionRef, error) {
	if s.versionsTTL > 0 {
		s.versionsMu.Lock()
		entry, ok := s.versionsCache[key]
		if ok && time.Since(entry.fetchedAt) < s.versionsTTL {
			s.versionsMu.Unlock()
			return entry.refs, nil
		}
		s.versionsMu.Unlock()
	}

	refs, err := hist.ListVersions(ctx)
	if err != nil {
		return nil, err
	}
	sortVersionsByCreated(refs)

	if s.versionsTTL > 0 {
		s.versionsMu.Lock()
		if s.versionsCache == nil {
			s.versionsCache = make(map[string]versionsCacheEntry)
		}
		s.versionsCache[key] = versionsCacheEntry{refs: refs, fetchedAt: time.Now()}
		s.versionsMu.Unlock()
	}
	return refs, nil
}

// AsOf resolves t to the index version that was live at that time, loads it, and
// returns a read-only Service bound to that snapshot. The returned Service
// exposes the full query API but its data never changes; watcher methods on it
// are inert.
//
// Resolution picks the newest version whose creation time is at or before t. If
// t predates the oldest retained version, ErrVersionNotAvailable is returned. If
// source does not implement HistoricalDataSource, ErrTimeTravelNotSupported is
// returned.
//
// Semantics: t is transaction/system time -- "the data as the system published
// it at t", NOT valid time. A correction or backfill published later does not
// appear at the real-world moment it became true. Use AsOf for audit, debugging,
// and point-in-time reconstruction, not as a source of valid-time business facts.
//
// Resolved snapshots are cached per Service (LRU, see WithHistoryCacheSize), so
// repeated AsOf calls that land on the same version avoid re-downloading.
func (s *Service) AsOf(ctx context.Context, source DataSource, t time.Time) (ServiceInterface, error) {
	hist, ok := source.(HistoricalDataSource)
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrTimeTravelNotSupported, source.String())
	}

	refs, err := s.listVersionsCached(ctx, hist, source.String())
	if err != nil {
		return nil, NewLoadError(source.String(), err)
	}

	ref, err := resolveVersion(refs, t)
	if err != nil {
		return nil, err
	}

	// Key the snapshot cache by source *and* version so a snapshot resolved
	// through, e.g., a redacting wrapper is never served to a raw source (or
	// vice versa) just because they share a generation ID.
	cacheKey := source.String() + "@" + ref.ID
	if cached := s.getCachedView(cacheKey); cached != nil {
		return cached, nil
	}

	reader, err := hist.LoadVersion(ctx, ref)
	if err != nil {
		return nil, NewLoadError(source.String(), err)
	}
	defer func() {
		if closeErr := reader.Close(); closeErr != nil {
			s.logger.Warn("failed to close reader", "source", source.String(), "error", closeErr)
		}
	}()

	view := NewService(WithLogger(s.logger))
	if err := view.loadFromReader(reader, cacheKey); err != nil {
		return nil, err
	}

	s.putCachedView(cacheKey, view)
	return view, nil
}

// resolveVersion returns the newest ref whose Created time is at or before t.
// Returns ErrVersionNotAvailable if refs is empty or t predates every ref.
func resolveVersion(refs []DataVersionRef, t time.Time) (DataVersionRef, error) {
	var (
		best     DataVersionRef
		found    bool
		earliest time.Time
	)
	for _, r := range refs {
		if earliest.IsZero() || r.Created.Before(earliest) {
			earliest = r.Created
		}
		if r.Created.After(t) {
			continue
		}
		if !found || r.Created.After(best.Created) {
			best = r
			found = true
		}
	}
	if !found {
		if earliest.IsZero() {
			return DataVersionRef{}, fmt.Errorf("%w: no versions retained", ErrVersionNotAvailable)
		}
		return DataVersionRef{}, fmt.Errorf("%w: requested %s predates earliest retained version %s",
			ErrVersionNotAvailable, t.UTC().Format(time.RFC3339), earliest.UTC().Format(time.RFC3339))
	}
	return best, nil
}

func sortVersionsByCreated(refs []DataVersionRef) {
	// Insertion against Created; stable enough for small-to-moderate version lists.
	for i := 1; i < len(refs); i++ {
		for j := i; j > 0 && refs[j].Created.Before(refs[j-1].Created); j-- {
			refs[j], refs[j-1] = refs[j-1], refs[j]
		}
	}
}

func (s *Service) getCachedView(key string) *Service {
	if s.historyCacheSize <= 0 {
		return nil
	}
	s.historyMu.Lock()
	defer s.historyMu.Unlock()
	view, ok := s.historyCache[key]
	if !ok {
		return nil
	}
	s.touchHistoryLocked(key)
	return view
}

func (s *Service) putCachedView(key string, view *Service) {
	if s.historyCacheSize <= 0 {
		return
	}
	s.historyMu.Lock()
	defer s.historyMu.Unlock()
	if s.historyCache == nil {
		s.historyCache = make(map[string]*Service)
	}
	if _, exists := s.historyCache[key]; !exists {
		s.historyOrder = append(s.historyOrder, key)
	}
	s.historyCache[key] = view
	s.touchHistoryLocked(key)

	// Evict oldest entries beyond the configured size.
	for len(s.historyOrder) > s.historyCacheSize {
		evict := s.historyOrder[0]
		s.historyOrder = s.historyOrder[1:]
		delete(s.historyCache, evict)
	}
}

// touchHistoryLocked moves key to the most-recently-used end of historyOrder.
// Must be called with historyMu held.
func (s *Service) touchHistoryLocked(key string) {
	for i, existing := range s.historyOrder {
		if existing == key {
			s.historyOrder = append(s.historyOrder[:i], s.historyOrder[i+1:]...)
			s.historyOrder = append(s.historyOrder, key)
			return
		}
	}
}
