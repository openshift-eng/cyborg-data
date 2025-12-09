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

