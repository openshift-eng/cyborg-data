"""Tests for the cohort accessors on Service.

Cohorts are modelled by the canonical ``HierarchyEntity`` (re-exported as
``Cohort``), identical in shape to teams/orgs/pillars/team_groups; the entity
type lives in ``group.type.name``, not a top-level field.
"""

from orgdatacore import (
    Cohort,
    Data,
    Group,
    GroupType,
    Lookups,
    Service,
)


def _service_with_cohorts(**cohorts: Cohort) -> Service:
    service = Service()
    service._data = Data(lookups=Lookups(cohorts=cohorts))
    return service


class TestCohortLookup:
    def test_get_existing_cohort(self):
        service = _service_with_cohorts(
            hcm=Cohort(name="HCM All", group=Group(type=GroupType(name="cohort"))),
        )
        result = service.get_cohort_by_name("hcm")
        assert result is not None
        assert result.name == "HCM All"
        assert result.group is not None
        assert result.group.type is not None
        assert result.group.type.name == "cohort"

    def test_get_nonexistent_cohort(self):
        assert _service_with_cohorts().get_cohort_by_name("nope") is None

    def test_get_cohort_without_data(self):
        assert Service().get_cohort_by_name("hcm") is None

    def test_get_all_cohorts_and_names(self):
        service = _service_with_cohorts(
            a=Cohort(name="A"),
            b=Cohort(name="B"),
        )
        assert len(service.get_all_cohorts()) == 2
        assert set(service.get_all_cohort_names()) == {"a", "b"}

    def test_get_all_cohorts_empty(self):
        assert _service_with_cohorts().get_all_cohorts() == []
        assert _service_with_cohorts().get_all_cohort_names() == []
