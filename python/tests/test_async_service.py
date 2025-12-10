"""Tests for the async service implementation."""

import asyncio
from collections.abc import Callable
from io import BytesIO
from typing import BinaryIO

import pytest

from orgdatacore import AsyncService, DataLoadError
from orgdatacore._internal.testing import create_test_data_json


class AsyncFakeDataSource:
    """Async fake data source for testing."""

    def __init__(self, data: str = "", load_error: Exception | None = None) -> None:
        self.data = data
        self.load_error = load_error

    async def load(self) -> BinaryIO:
        if self.load_error:
            raise self.load_error
        return BytesIO(self.data.encode("utf-8"))

    async def watch(self, callback: Callable[[], Exception | None]) -> Exception | None:
        return None

    def __str__(self) -> str:
        return "async-fake-data-source"


class TestAsyncService:
    """Tests for AsyncService."""

    @pytest.mark.asyncio
    async def test_load_from_async_data_source(self) -> None:
        """Test loading data from an async data source."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()

        await service.load_from_data_source(source)

        assert service.is_healthy()
        assert service.is_ready()

    @pytest.mark.asyncio
    async def test_get_employee_by_uid(self) -> None:
        """Test getting an employee by UID."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        employee = await service.get_employee_by_uid("testuser1")
        assert employee is not None
        assert employee.uid == "testuser1"
        assert employee.full_name == "Test User One"

    @pytest.mark.asyncio
    async def test_get_employee_by_email(self) -> None:
        """Test getting an employee by email."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        employee = await service.get_employee_by_email("testuser1@example.com")
        assert employee is not None
        assert employee.uid == "testuser1"

    @pytest.mark.asyncio
    async def test_get_employee_by_slack_uid(self) -> None:
        """Test getting an employee by Slack UID."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        employee = await service.get_employee_by_slack_uid("U111111")
        assert employee is not None
        assert employee.uid == "testuser1"

    @pytest.mark.asyncio
    async def test_get_team_by_name(self) -> None:
        """Test getting a team by name."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        team = await service.get_team_by_name("test-squad")
        assert team is not None
        assert team.name == "test-squad"

    @pytest.mark.asyncio
    async def test_get_all_employees(self) -> None:
        """Test getting all employees."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        employees = await service.get_all_employees()
        assert len(employees) == 2

    @pytest.mark.asyncio
    async def test_get_team_members(self) -> None:
        """Test getting team members."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        members = await service.get_team_members("test-squad")
        assert len(members) == 2

    @pytest.mark.asyncio
    async def test_get_user_teams(self) -> None:
        """Test getting user teams."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        teams = await service.get_user_teams("testuser1")
        assert "test-squad" in teams

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self) -> None:
        """Test that invalid JSON raises DataLoadError."""
        source = AsyncFakeDataSource(data='{"invalid": json}')
        service = AsyncService()

        with pytest.raises(DataLoadError):
            await service.load_from_data_source(source)

    @pytest.mark.asyncio
    async def test_load_error_raises_data_load_error(self) -> None:
        """Test that load errors are wrapped in DataLoadError."""
        source = AsyncFakeDataSource(load_error=OSError("Connection failed"))
        service = AsyncService()

        with pytest.raises(DataLoadError, match="Connection failed"):
            await service.load_from_data_source(source)

    @pytest.mark.asyncio
    async def test_health_check_without_data(self) -> None:
        """Test health check without data loaded."""
        service = AsyncService()
        assert not service.is_healthy()
        assert not service.is_ready()

    @pytest.mark.asyncio
    async def test_concurrent_reads(self) -> None:
        """Test concurrent read operations are safe."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        # Run many concurrent reads
        async def read_employee() -> None:
            for _ in range(10):
                await service.get_employee_by_uid("testuser1")
                await service.get_all_employees()

        tasks = [read_employee() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Should complete without errors
        assert service.is_healthy()

    @pytest.mark.asyncio
    async def test_get_employee_by_github_id(self) -> None:
        """Test getting an employee by GitHub ID."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        employee = await service.get_employee_by_github_id("ghuser1")
        assert employee is not None
        assert employee.uid == "testuser1"

    @pytest.mark.asyncio
    async def test_get_org_by_name(self) -> None:
        """Test getting an organization by name."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        org = await service.get_org_by_name("test-division")
        assert org is not None
        assert org.name == "test-division"

    @pytest.mark.asyncio
    async def test_get_pillar_by_name(self) -> None:
        """Test getting a pillar by name returns None when not found."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        # Test data doesn't have pillars
        pillar = await service.get_pillar_by_name("nonexistent-pillar")
        assert pillar is None

    @pytest.mark.asyncio
    async def test_get_team_group_by_name(self) -> None:
        """Test getting a team group by name returns None when not found."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        # Test data doesn't have team groups
        team_group = await service.get_team_group_by_name("nonexistent-team-group")
        assert team_group is None

    @pytest.mark.asyncio
    async def test_get_user_organizations(self) -> None:
        """Test getting user organizations."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        orgs = await service.get_user_organizations("testuser1")
        assert len(orgs) > 0

    @pytest.mark.asyncio
    async def test_get_all_teams(self) -> None:
        """Test getting all teams."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        teams = await service.get_all_teams()
        assert len(teams) > 0

    @pytest.mark.asyncio
    async def test_get_all_orgs(self) -> None:
        """Test getting all orgs."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        orgs = await service.get_all_orgs()
        assert len(orgs) > 0

    @pytest.mark.asyncio
    async def test_get_all_pillars(self) -> None:
        """Test getting all pillars (empty in test data)."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        pillars = await service.get_all_pillars()
        # Test data doesn't have pillars
        assert isinstance(pillars, tuple)

    @pytest.mark.asyncio
    async def test_get_all_team_groups(self) -> None:
        """Test getting all team groups (empty in test data)."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        team_groups = await service.get_all_team_groups()
        # Test data doesn't have team groups
        assert isinstance(team_groups, tuple)

    @pytest.mark.asyncio
    async def test_get_org_members(self) -> None:
        """Test getting org members."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        members = await service.get_org_members("test-division")
        assert isinstance(members, tuple)

    @pytest.mark.asyncio
    async def test_get_version(self) -> None:
        """Test getting version info (sync method on async service)."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        # get_version is synchronous, not async
        version = service.get_version()
        assert version.employee_count == 2
        assert version.org_count > 0

    @pytest.mark.asyncio
    async def test_initialize_with_data_source(self) -> None:
        """Test initializing service with data source."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService(data_source=source)
        await service.initialize()

        assert service.is_healthy()
        assert service.is_ready()

    @pytest.mark.asyncio
    async def test_queries_without_data(self) -> None:
        """Test that queries return None/empty without data loaded."""
        service = AsyncService()

        assert await service.get_employee_by_uid("test") is None
        assert await service.get_employee_by_email("test@test.com") is None
        assert await service.get_employee_by_slack_id("U123") is None
        assert await service.get_employee_by_github_id("gh123") is None
        assert await service.get_team_by_name("test") is None
        assert await service.get_org_by_name("test") is None
        assert await service.get_pillar_by_name("test") is None
        assert await service.get_team_group_by_name("test") is None
        assert await service.get_user_teams("test") == ()
        assert await service.get_user_organizations("test") == ()
        assert await service.get_all_employees() == ()
        assert await service.get_all_teams() == ()
        assert await service.get_all_orgs() == ()
        assert await service.get_all_pillars() == ()
        assert await service.get_all_team_groups() == ()
        assert await service.get_team_members("test") == ()
        assert await service.get_org_members("test") == ()

    @pytest.mark.asyncio
    async def test_start_watcher_returns_immediately(self) -> None:
        """Test that start_data_source_watcher returns immediately."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()

        # This should return immediately, not block
        await service.start_data_source_watcher(source)

        # Watcher task should be set
        assert service._watcher_task is not None
        assert service._watcher_running

        # Clean up
        await service.stop_watcher()

    @pytest.mark.asyncio
    async def test_stop_watcher_cancels_task(self) -> None:
        """Test that stop_watcher() cancels the watcher task."""

        class BlockingDataSource:
            """Data source with a blocking watch for testing."""

            def __init__(self, data: str) -> None:
                self.data = data
                self._stop_event = asyncio.Event()

            async def load(self) -> BinaryIO:
                return BytesIO(self.data.encode("utf-8"))

            async def watch(
                self, callback: Callable[[], Exception | None]
            ) -> Exception | None:
                # Block until cancelled
                try:
                    await self._stop_event.wait()
                except asyncio.CancelledError:
                    pass
                return None

            def __str__(self) -> str:
                return "blocking-data-source"

        source = BlockingDataSource(data=create_test_data_json())
        service = AsyncService()

        # Start watcher
        await service.start_data_source_watcher(source)

        # Verify watcher is running
        assert service._watcher_task is not None
        assert service._watcher_running
        assert not service._watcher_task.done()

        # Stop watcher
        await service.stop_watcher()

        # Verify watcher is stopped
        assert service._watcher_task is None
        assert not service._watcher_running

    @pytest.mark.asyncio
    async def test_watcher_already_running_raises_error(self) -> None:
        """Test that starting a watcher when one is running raises error."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()

        await service.start_data_source_watcher(source)

        with pytest.raises(RuntimeError, match="already running"):
            await service.start_data_source_watcher(source)

        # Clean up
        await service.stop_watcher()

    @pytest.mark.asyncio
    async def test_stop_watcher_calls_source_stop(self) -> None:
        """Test that stop_watcher() calls source.stop() if available."""
        stop_called = False

        class StoppableDataSource:
            """Data source with a stop() method for testing."""

            def __init__(self, data: str) -> None:
                self.data = data
                self._block_event = asyncio.Event()

            async def load(self) -> BinaryIO:
                return BytesIO(self.data.encode("utf-8"))

            async def watch(
                self, callback: Callable[[], Exception | None]
            ) -> Exception | None:
                # Block until stop is called
                await self._block_event.wait()
                return None

            def stop(self) -> None:
                nonlocal stop_called
                stop_called = True
                self._block_event.set()

            def __str__(self) -> str:
                return "stoppable-data-source"

        source = StoppableDataSource(data=create_test_data_json())
        service = AsyncService()

        await service.start_data_source_watcher(source)

        assert service._watcher_task is not None
        assert service._watcher_running

        await service.stop_watcher()

        assert stop_called, "source.stop() should have been called"
        assert service._watcher_task is None
        assert not service._watcher_running
