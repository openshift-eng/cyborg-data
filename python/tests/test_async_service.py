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
    async def test_get_employee_by_slack_id(self) -> None:
        """Test getting an employee by Slack ID."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        employee = await service.get_employee_by_slack_id("U111111")
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
        assert isinstance(pillars, list)

    @pytest.mark.asyncio
    async def test_get_all_team_groups(self) -> None:
        """Test getting all team groups (empty in test data)."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        team_groups = await service.get_all_team_groups()
        # Test data doesn't have team groups
        assert isinstance(team_groups, list)

    @pytest.mark.asyncio
    async def test_get_org_members(self) -> None:
        """Test getting org members."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        members = await service.get_org_members("test-division")
        assert isinstance(members, list)

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
        assert await service.get_user_teams("test") == []
        assert await service.get_user_organizations("test") == []
        assert await service.get_all_employees() == []
        assert await service.get_all_teams() == []
        assert await service.get_all_orgs() == []
        assert await service.get_all_pillars() == []
        assert await service.get_all_team_groups() == []
        assert await service.get_team_members("test") == []
        assert await service.get_org_members("test") == []
        assert await service.get_manager_for_employee("test") is None
        assert await service.is_employee_in_team("test", "team") is False
        assert await service.is_slack_user_in_team("U123", "team") is False
        assert await service.is_employee_in_org("test", "org") is False
        assert await service.is_slack_user_in_org("U123", "org") is False
        assert await service.get_all_employee_uids() == []
        assert await service.get_all_pillar_names() == []
        assert await service.get_all_team_group_names() == []
        assert await service.get_hierarchy_path("test", "team") == []
        assert await service.get_descendants_tree("test") is None
        assert await service.get_component_by_name("test") is None
        assert await service.get_all_components() == []
        assert await service.get_jira_projects() == []
        assert await service.get_jira_components("TEST") == []
        assert await service.get_teams_by_jira_project("TEST") == []
        assert await service.get_teams_by_jira_component("TEST", "Core") == []
        assert await service.get_jira_ownership_for_team("test") == []

    @pytest.mark.asyncio
    async def test_get_manager_for_employee(self) -> None:
        """Test getting an employee's manager."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        manager = await service.get_manager_for_employee("testuser1")
        assert manager is not None
        assert manager.uid == "testuser2"

        # testuser2 has no manager
        manager2 = await service.get_manager_for_employee("testuser2")
        assert manager2 is None

    @pytest.mark.asyncio
    async def test_get_teams_for_uid(self) -> None:
        """Test getting teams for a UID."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        teams = await service.get_teams_for_uid("testuser1")
        assert "test-squad" in teams

    @pytest.mark.asyncio
    async def test_get_teams_for_slack_id(self) -> None:
        """Test getting teams for a Slack ID."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        teams = await service.get_teams_for_slack_id("U111111")
        assert "test-squad" in teams

        # Nonexistent Slack ID
        teams2 = await service.get_teams_for_slack_id("U999999")
        assert teams2 == []

    @pytest.mark.asyncio
    async def test_is_employee_in_team(self) -> None:
        """Test checking if employee is in team."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        assert await service.is_employee_in_team("testuser1", "test-squad") is True
        assert await service.is_employee_in_team("testuser1", "nonexistent") is False
        assert await service.is_employee_in_team("nonexistent", "test-squad") is False

    @pytest.mark.asyncio
    async def test_is_slack_user_in_team(self) -> None:
        """Test checking if Slack user is in team."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        assert await service.is_slack_user_in_team("U111111", "test-squad") is True
        assert await service.is_slack_user_in_team("U111111", "nonexistent") is False
        assert await service.is_slack_user_in_team("U999999", "test-squad") is False

    @pytest.mark.asyncio
    async def test_is_employee_in_org(self) -> None:
        """Test checking if employee is in org."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        assert await service.is_employee_in_org("testuser1", "test-division") is True
        assert await service.is_employee_in_org("testuser1", "nonexistent") is False

    @pytest.mark.asyncio
    async def test_is_slack_user_in_org(self) -> None:
        """Test checking if Slack user is in org."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        assert await service.is_slack_user_in_org("U111111", "test-division") is True
        assert await service.is_slack_user_in_org("U999999", "test-division") is False

    @pytest.mark.asyncio
    async def test_get_all_employee_uids(self) -> None:
        """Test getting all employee UIDs."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        uids = await service.get_all_employee_uids()
        assert len(uids) == 2
        assert "testuser1" in uids
        assert "testuser2" in uids

    @pytest.mark.asyncio
    async def test_get_all_pillar_names(self) -> None:
        """Test getting all pillar names."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        names = await service.get_all_pillar_names()
        assert "test-pillar" in names

    @pytest.mark.asyncio
    async def test_get_all_team_group_names(self) -> None:
        """Test getting all team group names."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        names = await service.get_all_team_group_names()
        assert "test-team-group" in names

    @pytest.mark.asyncio
    async def test_get_hierarchy_path(self) -> None:
        """Test getting hierarchy path for an entity."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        path = await service.get_hierarchy_path("test-squad", "team")
        assert len(path) > 0
        assert path[0].name == "test-squad"
        assert path[0].type == "team"

    @pytest.mark.asyncio
    async def test_get_descendants_tree(self) -> None:
        """Test getting descendants tree for an entity."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        tree = await service.get_descendants_tree("test-division")
        assert tree is not None
        assert tree.name == "test-division"
        assert tree.type == "org"

    @pytest.mark.asyncio
    async def test_get_component_by_name(self) -> None:
        """Test getting a component by name."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        component = await service.get_component_by_name("test-component")
        assert component is not None
        assert component.name == "test-component"

        # Nonexistent
        assert await service.get_component_by_name("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_all_components(self) -> None:
        """Test getting all components."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        components = await service.get_all_components()
        assert len(components) == 1
        assert components[0].name == "test-component"

    @pytest.mark.asyncio
    async def test_get_jira_projects(self) -> None:
        """Test getting all Jira projects."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        projects = await service.get_jira_projects()
        assert "TEST" in projects
        assert "PLAT" in projects

    @pytest.mark.asyncio
    async def test_get_jira_components(self) -> None:
        """Test getting Jira components for a project."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        components = await service.get_jira_components("TEST")
        assert "Core" in components
        assert "_project_level" in components

        # Nonexistent project
        assert await service.get_jira_components("NONEXISTENT") == []

    @pytest.mark.asyncio
    async def test_get_teams_by_jira_project(self) -> None:
        """Test getting teams that own a Jira project."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        teams = await service.get_teams_by_jira_project("TEST")
        assert len(teams) > 0
        assert any(t.name == "test-squad" for t in teams)

    @pytest.mark.asyncio
    async def test_get_teams_by_jira_component(self) -> None:
        """Test getting teams that own a Jira component."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        teams = await service.get_teams_by_jira_component("TEST", "Core")
        assert len(teams) == 1
        assert teams[0].name == "test-squad"

        # Nonexistent
        assert await service.get_teams_by_jira_component("TEST", "Nonexistent") == []

    @pytest.mark.asyncio
    async def test_get_jira_ownership_for_team(self) -> None:
        """Test getting Jira ownership for a team."""
        source = AsyncFakeDataSource(data=create_test_data_json())
        service = AsyncService()
        await service.load_from_data_source(source)

        ownership = await service.get_jira_ownership_for_team("test-squad")
        assert len(ownership) > 0
        projects = [o["project"] for o in ownership]
        assert "TEST" in projects

        # Nonexistent team
        assert await service.get_jira_ownership_for_team("nonexistent") == []

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
