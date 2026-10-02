package orgdatacore

import (
	"context"
	"fmt"
	"time"
)

// ListVersions returns all retained versions of the index exposed by source,
// sorted oldest-first by creation time. The source must implement
// HistoricalDataSource; otherwise ErrTimeTravelNotSupported is returned.
func (s *Service) ListVersions(ctx context.Context, source DataSource) ([]DataVersionRef, error) {
	hist, ok := source.(HistoricalDataSource)
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrTimeTravelNotSupported, source.String())
	}
	refs, err := hist.ListVersions(ctx)
	if err != nil {
		return nil, NewLoadError(source.String(), err)
	}
	sortVersionsByCreated(refs)
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
// Resolved snapshots are cached per Service (LRU, see WithHistoryCacheSize), so
// repeated AsOf calls that land on the same version avoid re-downloading.
func (s *Service) AsOf(ctx context.Context, source DataSource, t time.Time) (ServiceInterface, error) {
	hist, ok := source.(HistoricalDataSource)
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrTimeTravelNotSupported, source.String())
	}

	refs, err := hist.ListVersions(ctx)
	if err != nil {
		return nil, NewLoadError(source.String(), err)
	}

	ref, err := resolveVersion(refs, t)
	if err != nil {
		return nil, err
	}

	if cached := s.getCachedView(ref.ID); cached != nil {
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
	sourceName := fmt.Sprintf("%s@%s", source.String(), ref.ID)
	if err := view.loadFromReader(reader, sourceName); err != nil {
		return nil, err
	}

	s.putCachedView(ref.ID, view)
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

func (s *Service) getCachedView(id string) *Service {
	if s.historyCacheSize <= 0 {
		return nil
	}
	s.historyMu.Lock()
	defer s.historyMu.Unlock()
	view, ok := s.historyCache[id]
	if !ok {
		return nil
	}
	s.touchHistoryLocked(id)
	return view
}

func (s *Service) putCachedView(id string, view *Service) {
	if s.historyCacheSize <= 0 {
		return
	}
	s.historyMu.Lock()
	defer s.historyMu.Unlock()
	if s.historyCache == nil {
		s.historyCache = make(map[string]*Service)
	}
	if _, exists := s.historyCache[id]; !exists {
		s.historyOrder = append(s.historyOrder, id)
	}
	s.historyCache[id] = view
	s.touchHistoryLocked(id)

	// Evict oldest entries beyond the configured size.
	for len(s.historyOrder) > s.historyCacheSize {
		evict := s.historyOrder[0]
		s.historyOrder = s.historyOrder[1:]
		delete(s.historyCache, evict)
	}
}

// touchHistoryLocked moves id to the most-recently-used end of historyOrder.
// Must be called with historyMu held.
func (s *Service) touchHistoryLocked(id string) {
	for i, existing := range s.historyOrder {
		if existing == id {
			s.historyOrder = append(s.historyOrder[:i], s.historyOrder[i+1:]...)
			s.historyOrder = append(s.historyOrder, id)
			return
		}
	}
}
