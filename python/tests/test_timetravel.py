"""Tests for the time-travel (as_of) API."""

from datetime import UTC, datetime, timedelta

import pytest

from orgdatacore import (
    AnonymizingDataSource,
    AsyncService,
    RedactingDataSource,
    Service,
    TimeTravelNotSupportedError,
    VersionNotAvailableError,
)
from orgdatacore._internal.testing import FakeGCSDataSource
from orgdatacore._types import PIIMode


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
        calls = {"n": 0}
        original = history.list_versions

        def counting():  # type: ignore[no-untyped-def]
            calls["n"] += 1
            return original()

        history.list_versions = counting  # type: ignore[method-assign]
        svc = Service()
        svc.as_of(history, t0 + timedelta(hours=12))
        svc.as_of(history, t0 + timedelta(hours=36))
        assert calls["n"] == 1

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
