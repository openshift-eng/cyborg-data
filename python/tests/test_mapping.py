"""Tests for pydantic model validation and serialization behavior.

Replaces the old _mapping.py unit tests. Validates that pydantic models
correctly handle JSON parsing, aliased fields, defaults, and round-trips.
"""

import pytest
from pydantic import ValidationError

from orgdatacore._types import (
    Component,
    Employee,
    Group,
    GroupType,
    RepoInfo,
    RoleInfo,
    Team,
)


class TestModelValidate:
    """Tests for Model.model_validate() (JSON dict -> model)."""

    def test_employee_full_data(self):
        data = {
            "uid": "jsmith",
            "full_name": "John Smith",
            "email": "jsmith@example.com",
            "job_title": "Engineer",
            "slack_uid": "U123",
            "github_id": "jsmith-gh",
            "rhat_geo": "NA",
            "cost_center": 42,
            "manager_uid": "mgr1",
            "is_people_manager": True,
            "timezone": "US/Eastern",
        }
        emp = Employee.model_validate(data)
        assert emp.uid == "jsmith"
        assert emp.full_name == "John Smith"
        assert emp.cost_center == 42
        assert emp.is_people_manager is True

    def test_employee_missing_fields_uses_defaults(self):
        emp = Employee.model_validate({"uid": "x"})
        assert emp.uid == "x"
        assert emp.full_name == ""
        assert emp.cost_center == 0
        assert emp.is_people_manager is False

    def test_employee_empty_dict(self):
        emp = Employee.model_validate({})
        assert emp.uid == ""

    def test_nested_model_validation(self):
        data = {
            "uid": "t1",
            "name": "Team One",
            "type": "team",
            "group": {
                "type": {"name": "dev"},
                "resolved_people_uid_list": ["a", "b"],
            },
        }
        team = Team.model_validate(data)
        assert team.group.type.name == "dev"
        assert team.group.resolved_people_uid_list == ("a", "b")


class TestAliasedFields:
    """Tests for fields with JSON aliases."""

    def test_repo_info_alias(self):
        """repo_name in JSON maps to repo in Python."""
        data = {"repo_name": "my-repo", "description": "A repo"}
        repo = RepoInfo.model_validate(data)
        assert repo.repo == "my-repo"
        assert repo.description == "A repo"

    def test_repo_info_by_python_name(self):
        """Can also construct by Python field name."""
        repo = RepoInfo(repo="my-repo")
        assert repo.repo == "my-repo"

    def test_group_resolved_roles_alias(self):
        """resolved_roles in JSON maps to roles in Python."""
        data = {
            "type": {"name": "dev"},
            "resolved_people_uid_list": [],
            "resolved_roles": [
                {"people": ["u1"], "roles": ["lead"], "description": ""}
            ],
        }
        group = Group.model_validate(data)
        assert len(group.roles) == 1
        assert group.roles[0].people == ("u1",)


class TestModelDump:
    """Tests for model_dump() (model -> dict)."""

    def test_repo_info_dump_by_alias(self):
        repo = RepoInfo(repo="my-repo", description="desc")
        d = repo.model_dump(by_alias=True)
        assert d["repo_name"] == "my-repo"
        assert "repo" not in d

    def test_repo_info_dump_by_name(self):
        repo = RepoInfo(repo="my-repo")
        d = repo.model_dump()
        assert d["repo"] == "my-repo"

    def test_group_dump_by_alias(self):
        group = Group(
            type=GroupType(name="dev"),
            roles=(RoleInfo(people=("u1",), roles=("lead",)),),
        )
        d = group.model_dump(by_alias=True)
        assert "resolved_roles" in d
        assert "roles" not in d


class TestComponentNestedValidation:
    """Tests for Component's model_validator that flattens nested 'component' key."""

    def test_flat_format(self):
        data = {
            "name": "comp1",
            "type": "library",
            "repos": [{"repo_name": "r1"}],
        }
        comp = Component.model_validate(data)
        assert comp.name == "comp1"
        assert comp.type == "library"
        assert len(comp.repos) == 1
        assert comp.repos[0].repo == "r1"

    def test_nested_format(self):
        data = {
            "name": "comp2",
            "component": {
                "type": {"name": "service"},
                "repos": [{"repo_name": "r2"}],
                "jiras": [{"project": "PROJ", "component": "c1"}],
                "repos_list": ["repo-a"],
            },
        }
        comp = Component.model_validate(data)
        assert comp.name == "comp2"
        assert comp.type == "service"
        assert len(comp.repos) == 1
        assert comp.repos[0].repo == "r2"
        assert len(comp.jiras) == 1
        assert comp.jiras[0].project == "PROJ"
        assert comp.repos_list == ("repo-a",)

    def test_nested_type_string(self):
        data = {
            "name": "comp3",
            "component": {"type": "simple-type"},
        }
        comp = Component.model_validate(data)
        assert comp.type == "simple-type"

    def test_flat_overrides_nested(self):
        data = {
            "name": "comp4",
            "type": "flat-type",
            "component": {"type": {"name": "nested-type"}},
        }
        comp = Component.model_validate(data)
        assert comp.type == "flat-type"


class TestRoundTrip:
    """Tests for validate -> dump -> validate round-trip."""

    def test_employee_round_trip(self):
        data = {
            "uid": "jsmith",
            "full_name": "John Smith",
            "email": "j@x.com",
            "job_title": "Eng",
            "slack_uid": "U1",
            "github_id": "gh1",
            "cost_center": 5,
            "is_people_manager": True,
        }
        emp = Employee.model_validate(data)
        dumped = emp.model_dump()
        emp2 = Employee.model_validate(dumped)
        assert emp == emp2

    def test_team_round_trip(self):
        data = {
            "uid": "t1",
            "name": "Team",
            "type": "team",
            "group": {
                "type": {"name": "dev"},
                "resolved_people_uid_list": ["a"],
                "resolved_roles": [
                    {"people": ["a"], "roles": ["lead"], "description": ""}
                ],
                "repos": [{"repo_name": "r1", "description": ""}],
                "jiras": [{"project": "P", "component": "C"}],
            },
            "parent": {"name": "org1", "type": "org"},
        }
        team = Team.model_validate(data)
        dumped = team.model_dump(by_alias=True)
        team2 = Team.model_validate(dumped)
        assert team == team2


class TestFrozenModels:
    """Tests for frozen model immutability."""

    def test_employee_is_frozen(self):
        emp = Employee(uid="x")
        with pytest.raises(ValidationError):
            emp.uid = "y"  # type: ignore[misc]
        assert emp.uid == "x"

    def test_model_copy_creates_new_instance(self):
        emp = Employee(uid="x", full_name="Original")
        emp2 = emp.model_copy(update={"full_name": "Updated"})
        assert emp.full_name == "Original"
        assert emp2.full_name == "Updated"
        assert emp.uid == emp2.uid
