"""Tests for the time-travel (as_of) API."""

from datetime import UTC, datetime, timedelta

import pytest

from orgdatacore import (
    AnonymizingDataSource,
    AsyncService,
    DataLoadError,
    ReadOnlyViewError,
    RedactingDataSource,
    Service,
    TimeTravelNotSupportedError,
    VersionNotAvailableError,
)
from orgdatacore._internal.testing import FakeGCSDataSource
from orgdatacore._types import DataVersionRef, PIIMode


def _version_json(data_version: str, emp_uid: str) -> str:
    """Build a minimal valid index with a distinguishable version and employee."""
    return (
        '{'
        f'"metadata": {{"generated_at": "{data_version}", "data_version": "{data_version}"}},'
        '"lookups": {'
        f'"employees": {{"{emp_uid}": {{"uid": "{emp_uid}", "full_name": "User", '
        '"email": "u@test.com", "job_title": "Dev"}},'
        '"teams": {}, "orgs": {}},'
        '"indexes": {'
        f'"membership": {{"membership_index": {{"{emp_uid}": []}}, "relationship_index": {{}}}},'
        '"slack_id_mappings": {"slack_uid_to_uid": {}},'
        '"github_id_mappings": {"github_id_to_uid": {}}}}'
    )


@pytest.fixture
def t0() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0)


@pytest.fixture
def history(t0: datetime) -> FakeGCSDataSource:
    """A fake source with three versions: v1 (t0), v2 (t0+24h), v3 (t0+48h)."""
    src = FakeGCSDataSource(
        bucket="bucket",
        object_path="org.json",
        content=_version_json("v1", "emp1"),
        created=t0,
    )
    src.add_version_at(_version_json("v2", "emp2"), t0 + timedelta(hours=24))
    src.add_version_at(_version_json("v3", "emp3"), t0 + timedelta(hours=48))
    return src


class TestAsOf:
    """Tests for Service.as_of."""

    @pytest.mark.parametrize(
        "offset_hours,want_version,want_emp",
        [
            (0, "v1", "emp1"),
            (12, "v1", "emp1"),
            (24, "v2", "emp2"),
            (36, "v2", "emp2"),
            (100, "v3", "emp3"),
        ],
    )
    def test_resolves_version_live_at_time(
        self,
        history: FakeGCSDataSource,
        t0: datetime,
        offset_hours: int,
        want_version: str,
        want_emp: str,
    ) -> None:
        svc = Service()
        view = svc.as_of(history, t0 + timedelta(hours=offset_hours))
        assert view.get_data_version() == want_version
        assert view.get_employee_by_uid(want_emp) is not None

    def test_before_earliest_raises(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        svc = Service()
        with pytest.raises(VersionNotAvailableError):
            svc.as_of(history, t0 - timedelta(hours=1))

    def test_non_historical_source_raises(self) -> None:
        # A plain object implementing only DataSource (no history).
        class PlainSource:
            def load(self):  # type: ignore[no-untyped-def]
                from io import BytesIO

                return BytesIO(_version_json("v1", "emp1").encode())

            def watch(self, callback):  # type: ignore[no-untyped-def]
                return None

            def __str__(self) -> str:
                return "plain"

        svc = Service()
        with pytest.raises(TimeTravelNotSupportedError):
            svc.as_of(PlainSource(), datetime.now())
        with pytest.raises(TimeTravelNotSupportedError):
            svc.list_versions(PlainSource())

    def test_caches_resolved_snapshot(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        svc = Service()
        first = svc.as_of(history, t0 + timedelta(hours=12))
        # Different time, same resolved version (v1) -> cached instance.
        second = svc.as_of(history, t0 + timedelta(hours=6))
        assert first is second

    def test_cache_disabled(self, history: FakeGCSDataSource, t0: datetime) -> None:
        svc = Service(history_cache_size=0)
        first = svc.as_of(history, t0)
        second = svc.as_of(history, t0)
        assert first is not second


class TestReviewFixes:
    """Regression tests for the issues CodeRabbit flagged."""

    def test_timezone_aware_time_does_not_raise(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        # Fixture created times are naive; a tz-aware request must not TypeError.
        svc = Service()
        aware = t0.replace(tzinfo=UTC) + timedelta(hours=12)
        view = svc.as_of(history, aware)
        assert view.get_data_version() == "v1"

    def test_cache_key_isolates_wrapped_sources(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        # A redacting wrapper must not be served the cached unredacted snapshot
        # just because it shares a version id with the raw source (PII leak).
        svc = Service()
        raw_view = svc.as_of(history, t0)
        assert raw_view.get_employee_by_uid("emp1").full_name == "User"

        redacting = RedactingDataSource(history, PIIMode.REDACTED)
        red_view = svc.as_of(redacting, t0)
        assert red_view.get_employee_by_uid("emp1").full_name == "[REDACTED]"

    def test_version_listing_is_cached(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        counting = _CountingHistory(history)
        svc = Service()
        svc.as_of(counting, t0 + timedelta(hours=12))
        svc.as_of(counting, t0 + timedelta(hours=36))
        assert counting.list_versions_calls == 1

    def test_anonymize_load_version_preserves_live_state(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        anon = AnonymizingDataSource(history, PIIMode.ANONYMIZED)
        svc = Service()
        svc.load_from_data_source(anon)  # live load builds nonce tables
        before = anon.uid_to_nonce_map
        assert before

        svc.as_of(anon, t0)  # historical load through the same wrapper
        assert anon.uid_to_nonce_map == before

    def test_as_of_propagates_pruned_version(self, t0: datetime) -> None:
        # A version resolved from the listing but pruned before read surfaces as
        # VersionNotAvailableError, not a generic DataLoadError.
        from io import BytesIO

        from orgdatacore._types import DataVersionRef

        class PrunedSource:
            def load(self):  # type: ignore[no-untyped-def]
                return BytesIO(_version_json("v1", "emp1").encode())

            def watch(self, callback):  # type: ignore[no-untyped-def]
                return None

            def __str__(self) -> str:
                return "pruned"

            def list_versions(self) -> list[DataVersionRef]:
                return [DataVersionRef(id="1", created=t0)]

            def load_version(self, ref: DataVersionRef) -> BytesIO:
                raise VersionNotAvailableError("generation 1 no longer retained")

        svc = Service()
        with pytest.raises(VersionNotAvailableError):
            svc.as_of(PrunedSource(), t0)


class TestListVersions:
    """Tests for Service.list_versions."""

    def test_sorted_oldest_first(
        self, history: FakeGCSDataSource
    ) -> None:
        svc = Service()
        refs = svc.list_versions(history)
        assert len(refs) == 3
        assert [r.created for r in refs] == sorted(r.created for r in refs)


class TestAsOfThroughWrappers:
    """Time travel must work through redaction wrappers."""

    def test_through_redacting_source(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        redacting = RedactingDataSource(history, PIIMode.REDACTED)
        svc = Service()
        view = svc.as_of(redacting, t0)
        emp = view.get_employee_by_uid("emp1")
        assert emp is not None
        assert emp.full_name == "[REDACTED]"

    def test_through_redacting_non_historical_source(self) -> None:
        bare = FakeGCSDataSource(
            bucket="bucket",
            object_path="org.json",
            content=_version_json("v1", "emp1"),
        )

        # Strip history support so the wrapped source is not historical.
        class _NoHistory:
            def __init__(self, inner: FakeGCSDataSource) -> None:
                self._inner = inner

            def load(self):  # type: ignore[no-untyped-def]
                return self._inner.load()

            def watch(self, callback):  # type: ignore[no-untyped-def]
                return None

            def __str__(self) -> str:
                return str(self._inner)

        redacting = RedactingDataSource(_NoHistory(bare), PIIMode.REDACTED)
        svc = Service()
        with pytest.raises(TimeTravelNotSupportedError):
            svc.as_of(redacting, datetime.now())


class TestAsyncAsOf:
    """Time travel on AsyncService (works with sync historical sources too)."""

    @pytest.mark.asyncio
    async def test_resolves_version_live_at_time(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        svc = AsyncService()
        view = await svc.as_of(history, t0 + timedelta(hours=36))
        assert view.get_data_version() == "v2"
        assert await view.get_employee_by_uid("emp2") is not None

    @pytest.mark.asyncio
    async def test_before_earliest_raises(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        svc = AsyncService()
        with pytest.raises(VersionNotAvailableError):
            await svc.as_of(history, t0 - timedelta(hours=1))

    @pytest.mark.asyncio
    async def test_caches_resolved_snapshot(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        svc = AsyncService()
        first = await svc.as_of(history, t0 + timedelta(hours=12))
        second = await svc.as_of(history, t0 + timedelta(hours=6))
        assert first is second


class _CountingHistory:
    """Historical source that counts list_versions calls, wrapping a real source.

    A real fake collaborator (not a monkeypatch) so the cache behavior is driven
    through the actual object, mirroring the Go countingHistorical fake.
    """

    def __init__(self, inner: FakeGCSDataSource) -> None:
        self._inner = inner
        self.list_versions_calls = 0

    def load(self):  # type: ignore[no-untyped-def]
        return self._inner.load()

    def watch(self, callback):  # type: ignore[no-untyped-def]
        return None

    def __str__(self) -> str:
        return str(self._inner)

    def list_versions(self) -> list[DataVersionRef]:
        self.list_versions_calls += 1
        return self._inner.list_versions()

    def load_version(self, ref: DataVersionRef) -> object:
        return self._inner.load_version(ref)


class _MixedTZHistory:
    """Historical source whose refs mix naive and tz-aware created times."""

    def __init__(self, t0: datetime) -> None:
        self._t0 = t0

    def load(self):  # type: ignore[no-untyped-def]
        from io import BytesIO

        return BytesIO(_version_json("v1", "emp1").encode())

    def watch(self, callback):  # type: ignore[no-untyped-def]
        return None

    def __str__(self) -> str:
        return "mixed-tz"

    def list_versions(self) -> list[DataVersionRef]:
        # One naive (DataVersionRef default is datetime.min, naive) and one aware.
        return [
            DataVersionRef(id="1"),  # naive datetime.min
            DataVersionRef(id="2", created=self._t0.replace(tzinfo=UTC)),
        ]

    def load_version(self, ref: DataVersionRef) -> object:
        from io import BytesIO

        return BytesIO(_version_json("v1", "emp1").encode())


class _LoadVersionFails:
    """Historical source whose load_version raises a generic (non-version) error."""

    def __init__(self, t0: datetime) -> None:
        self._t0 = t0

    def load(self):  # type: ignore[no-untyped-def]
        from io import BytesIO

        return BytesIO(_version_json("v1", "emp1").encode())

    def watch(self, callback):  # type: ignore[no-untyped-def]
        return None

    def __str__(self) -> str:
        return "load-fails"

    def list_versions(self) -> list[DataVersionRef]:
        return [DataVersionRef(id="1", created=self._t0)]

    def load_version(self, ref: DataVersionRef) -> object:
        raise RuntimeError("transient read failure")


class TestReadOnlyView:
    """A historical view is shared and immutable; its mutators must refuse."""

    def test_sync_load_refused(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        svc = Service()
        view = svc.as_of(history, t0)
        with pytest.raises(ReadOnlyViewError):
            view.load_from_data_source(history)
        with pytest.raises(ReadOnlyViewError):
            view.start_data_source_watcher(history)
        # Snapshot untouched by the refused mutations.
        assert view.get_data_version() == "v1"

    @pytest.mark.asyncio
    async def test_async_load_refused(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        svc = AsyncService()
        view = await svc.as_of(history, t0)
        with pytest.raises(ReadOnlyViewError):
            await view.load_from_data_source(history)
        with pytest.raises(ReadOnlyViewError):
            await view.start_data_source_watcher(history)
        assert view.get_data_version() == "v1"


class TestMixedTimezoneListing:
    """list_versions must tolerate mixed naive/aware created times when sorting."""

    def test_sync_does_not_raise(self, t0: datetime) -> None:
        svc = Service()
        refs = svc.list_versions(_MixedTZHistory(t0))
        assert len(refs) == 2

    @pytest.mark.asyncio
    async def test_async_does_not_raise(self, t0: datetime) -> None:
        svc = AsyncService()
        refs = await svc.list_versions(_MixedTZHistory(t0))
        assert len(refs) == 2


class TestAsyncLoadVersionErrorWrapping:
    """Async as_of must wrap generic load_version failures in DataLoadError,
    matching the sync API's documented contract."""

    @pytest.mark.asyncio
    async def test_generic_failure_becomes_dataloaderror(self, t0: datetime) -> None:
        svc = AsyncService()
        with pytest.raises(DataLoadError):
            await svc.as_of(_LoadVersionFails(t0), t0)


class TestAsyncWrapperTimeTravel:
    """Time travel must work through the async redaction/anonymization wrappers,
    as the sync wrappers already do."""

    @pytest.mark.asyncio
    async def test_through_async_redacting_wrapper(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        from orgdatacore import AsyncRedactingDataSource

        wrapped = AsyncRedactingDataSource(history, PIIMode.REDACTED)
        svc = AsyncService()

        refs = await svc.list_versions(wrapped)
        assert len(refs) == 3

        view = await svc.as_of(wrapped, t0)
        emp = await view.get_employee_by_uid("emp1")
        assert emp is not None
        assert emp.full_name == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_through_async_anonymizing_wrapper(
        self, history: FakeGCSDataSource, t0: datetime
    ) -> None:
        from orgdatacore import AsyncAnonymizingDataSource

        wrapped = AsyncAnonymizingDataSource(history, PIIMode.ANONYMIZED)
        svc = AsyncService()

        refs = await svc.list_versions(wrapped)
        assert len(refs) == 3

        # Resolves and loads the snapshot (uids are anonymized to nonces, so we
        # assert on the resolved producer version rather than a known uid).
        view = await svc.as_of(wrapped, t0)
        assert view.get_data_version() == "v1"


class TestAsyncValidation:
    """Async load/as_of must enforce the same structural invariants as sync/Go."""

    @pytest.mark.asyncio
    async def test_async_rejects_pii_free_with_employees(self, t0: datetime) -> None:
        # pii_free set but employees populated -> invalid; sync and Go reject it.
        bad = (
            '{"metadata": {"generated_at": "v1", "data_version": "v1", '
            '"pii_free": true},'
            '"lookups": {"employees": {"emp1": {"uid": "emp1", '
            '"full_name": "User", "email": "u@test.com", "job_title": "Dev"}},'
            '"teams": {}, "orgs": {}},'
            '"indexes": {'
            '"membership": {"membership_index": {}, "relationship_index": {}},'
            '"slack_id_mappings": {"slack_uid_to_uid": {}},'
            '"github_id_mappings": {"github_id_to_uid": {}}}}'
        )

        class _BadSource:
            def load(self):  # type: ignore[no-untyped-def]
                from io import BytesIO

                return BytesIO(bad.encode())

            def watch(self, callback):  # type: ignore[no-untyped-def]
                return None

            def __str__(self) -> str:
                return "bad"

        svc = AsyncService()
        with pytest.raises(DataLoadError):
            await svc.load_from_data_source(_BadSource())
