# Changelog — orgdatacore (Go)

All notable changes to the Go package are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this package follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-13

### Added

- **Time-travel API** for point-in-time historical queries (OCPCRT-770):
  - `Service.AsOf(ctx, source, t)` resolves `t` to the index version live at
    that time and returns a read-only `ServiceInterface` bound to that snapshot.
    Resolution picks the newest version whose creation time is at or before `t`;
    a time predating the oldest retained version returns `ErrVersionNotAvailable`.
    `t` is transaction/system time, not valid time.
  - `Service.ListVersions(ctx, source)` lists all retained versions,
    sorted oldest-first.
  - `HistoricalDataSource` interface (`ListVersions`, `LoadVersion`) and the
    `DataVersionRef` type.
  - `GCSDataSource` implements `HistoricalDataSource` via object versioning; the
    redacting and anonymizing wrappers pass history through so time travel works
    through them.
- Service options: `WithHistoryCacheSize` (LRU snapshot cache) and
  `WithVersionsCacheTTL` (version-listing TTL cache).
- Errors: `ErrTimeTravelNotSupported`, `ErrVersionNotAvailable`, and
  `ErrReadOnlyView`.

### Fixed

- Version listings are sorted stably and copied before sorting, so versions
  sharing a `Created` timestamp resolve deterministically (matching Python) and
  a source-owned slice is never mutated.
- `RedactingDataSource.String()` reflects redaction for any non-`PIIModeFull`
  mode, so the `AsOf` snapshot/version caches can never serve an unredacted
  snapshot to a caller that asked for redaction.
- Added compile-time `HistoricalDataSource` assertions for the GCS sources and
  the redaction/anonymization wrappers to catch signature drift at build time.

### Notes

- **Read-only snapshots.** A `Service` returned by `AsOf` is bound to an
  immutable snapshot shared across callers. Its mutating methods
  (`LoadFromDataSource`, `StartDataSourceWatcher`) return `ErrReadOnlyView`
  rather than overwriting the shared snapshot. Normally constructed services are
  unaffected.
- **Timezone handling.** Version resolution and listing compare creation times
  in UTC, so a request time in any location resolves correctly.
</content>
