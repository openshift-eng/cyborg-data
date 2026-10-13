# Changelog — orgdatacore (Python)

All notable changes to the Python package are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this package follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-10-13

### Added

- **Time-travel API** for point-in-time historical queries (OCPCRT-770):
  - `Service.as_of(source, t)` and `AsyncService.as_of(source, t)` resolve `t`
    to the index version live at that time and return a read-only service bound
    to that snapshot. Resolution picks the newest version whose creation time is
    at or before `t`; a time predating the oldest retained version raises
    `VersionNotAvailableError`. `t` is transaction/system time, not valid time.
  - `Service.list_versions(source)` / `AsyncService.list_versions(source)` list
    all retained versions, sorted oldest-first.
  - `HistoricalDataSource` protocol (`list_versions`, `load_version`) and the
    `DataVersionRef` type.
  - `GCSDataSource` and `AsyncGCSDataSource` implement the historical protocol
    via object versioning; the redacting and anonymizing wrappers pass history
    through so time travel works through them.
- `Service` / `AsyncService` constructor parameters: `history_cache_size` (LRU
  snapshot cache) and `versions_cache_ttl` (version-listing TTL cache).
- Exceptions: `TimeTravelNotSupportedError`, `VersionNotAvailableError`, and
  `ReadOnlyViewError` (all exported from `orgdatacore`).

### Fixed

- Naive request datetimes are interpreted as system local time (not UTC) when
  resolving `as_of`/`list_versions`, so a naive `datetime.now()` resolves to the
  correct instant on non-UTC hosts (matching Go's absolute `time.Now()`).
- The async redaction/anonymization wrappers (`AsyncRedactingDataSource`,
  `AsyncAnonymizingDataSource`) now support time travel (`list_versions` /
  `load_version`), matching the sync wrappers.
- `AsyncService.load_from_data_source` / `as_of` now validate the loaded data
  structure (e.g. `pii_free` invariants), matching the sync and Go loaders.

### Notes

- **Read-only snapshots.** A service returned by `as_of` is bound to an
  immutable snapshot shared across callers. Its mutating methods
  (`load_from_data_source`, `start_data_source_watcher`) raise
  `ReadOnlyViewError` rather than overwriting the shared snapshot. Normally
  constructed services are unaffected.
- **Timezone handling.** Version resolution and listing normalize naive and
  timezone-aware datetimes to UTC, so passing a naive request time (e.g.
  `datetime.now()`) against tz-aware GCS timestamps resolves correctly instead
  of raising `TypeError`.
</content>
