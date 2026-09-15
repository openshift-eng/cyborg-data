"""Regression tests for stable-ID hierarchy traversal (OCPCRT-653).

An index where a team and a team_group share the name "shared", disambiguated
by stable IDs and linked by parent_id:

    acme(org, o1) -> shared(team_group, g1) -> shared(team, t1) -> leaf(team, l1)
"""

import io
import json

import pytest

from orgdatacore import AsyncService, Service
from orgdatacore._types import OrgInfoType

COLLISION_INDEX = {
    "metadata": {},
    "lookups": {
        "employees": {"euser": {"uid": "euser"}},
        "orgs": {"acme": {"name": "acme", "type": "org", "stable_id": "o1"}},
        "team_groups": {
            "shared": {
                "name": "shared",
                "type": "team_group",
                "stable_id": "g1",
                "parent": {"name": "acme", "type": "org"},
                "parent_id": "o1",
            }
        },
        "teams": {
            "shared": {
                "name": "shared",
                "type": "team",
                "stable_id": "t1",
                "parent": {"name": "shared", "type": "team_group"},
                "parent_id": "g1",
            },
            "leaf": {
                "name": "leaf",
                "type": "team",
                "stable_id": "l1",
                "parent": {"name": "shared", "type": "team"},
                "parent_id": "t1",
            },
        },
    },
    "indexes": {
        "membership": {
            "membership_index": {
                "euser": [{"name": "shared", "type": "team", "stable_id": "t1"}]
            }
        },
        "slack_id_mappings": {"slack_uid_to_uid": {"Suser": "euser"}},
    },
}

# A minimal index with no stable ids, to exercise the legacy fallback path.
LEGACY_INDEX = {
    "metadata": {},
    "lookups": {
        "employees": {"euser": {"uid": "euser"}},
        "orgs": {"acme": {"name": "acme", "type": "org"}},
        "team_groups": {
            "grp": {
                "name": "grp",
                "type": "team_group",
                "parent": {"name": "acme", "type": "org"},
            }
        },
        "teams": {
            "t": {"name": "t", "type": "team", "parent": {"name": "grp", "type": "team_group"}}
        },
    },
    "indexes": {
        "membership": {"membership_index": {"euser": [{"name": "t", "type": "team"}]}}
    },
}


class _DictSource:
    def __init__(self, data: dict):
        self._raw = json.dumps(data).encode()

    def load(self) -> io.BytesIO:
        return io.BytesIO(self._raw)

    def __str__(self) -> str:
        return "dict-source"


class _AsyncDictSource(_DictSource):
    async def load(self) -> io.BytesIO:  # type: ignore[override]
        return io.BytesIO(self._raw)


@pytest.fixture
def collision_service() -> Service:
    svc = Service()
    svc.load_from_data_source(_DictSource(COLLISION_INDEX))
    assert svc._use_stable_ids is True
    return svc


class TestSyncStableIDCollision:
    def test_explicit_team_group_resolves(self, collision_service: Service):
        path = collision_service.get_hierarchy_path("shared", "team_group")
        assert [(e.name, e.type, e.stable_id) for e in path] == [
            ("shared", "team_group", "g1"),
            ("acme", "org", "o1"),
        ]

    def test_team_ascends_through_same_named_group(self, collision_service: Service):
        path = collision_service.get_hierarchy_path("shared", "team")
        assert [(e.name, e.type, e.stable_id) for e in path] == [
            ("shared", "team", "t1"),
            ("shared", "team_group", "g1"),
            ("acme", "org", "o1"),
        ]

    def test_descendants_keep_same_named_nodes_distinct(
        self, collision_service: Service
    ):
        tree = collision_service.get_descendants_tree("acme")
        assert tree is not None
        assert len(tree.children) == 1
        tg = tree.children[0]
        assert (tg.name, tg.type, tg.stable_id) == ("shared", "team_group", "g1")
        assert len(tg.children) == 1
        team = tg.children[0]
        assert (team.name, team.type, team.stable_id) == ("shared", "team", "t1")
        assert [c.name for c in team.children] == ["leaf"]

    def test_user_organizations_distinct_by_type(self, collision_service: Service):
        orgs = collision_service.get_user_organizations("Suser")
        assert [(o.name, o.type, o.stable_id) for o in orgs] == [
            ("shared", OrgInfoType.TEAM, "t1"),
            ("shared", OrgInfoType.TEAM_GROUP, "g1"),
            ("acme", OrgInfoType.ORGANIZATION, "o1"),
        ]

    def test_is_employee_in_org_via_hierarchy(self, collision_service: Service):
        assert collision_service.is_employee_in_org("euser", "acme") is True


# Indexes that carry stable ids but are malformed; both must fall back to legacy.
DUPLICATE_ID_INDEX = {
    "metadata": {},
    "lookups": {
        "employees": {"euser": {"uid": "euser"}},
        "orgs": {"acme": {"name": "acme", "type": "org", "stable_id": "dupe"}},
        "teams": {"t": {"name": "t", "type": "team", "stable_id": "dupe"}},
    },
    "indexes": {
        "membership": {"membership_index": {"euser": [{"name": "t", "type": "team"}]}}
    },
}

DANGLING_PARENT_INDEX = {
    "metadata": {},
    "lookups": {
        "employees": {"euser": {"uid": "euser"}},
        "teams": {
            "t": {
                "name": "t",
                "type": "team",
                "stable_id": "t1",
                "parent": {"name": "ghost", "type": "org"},
                "parent_id": "missing",
            }
        },
    },
    "indexes": {
        "membership": {"membership_index": {"euser": [{"name": "t", "type": "team"}]}}
    },
}


# Legacy index whose team has a parent with an unknown/empty type. The legacy
# hierarchy walk surfaces that entry; resolving it must not raise.
BOGUS_PARENT_INDEX = {
    "metadata": {},
    "lookups": {
        "employees": {"euser": {"uid": "euser"}},
        "teams": {
            "t": {"name": "t", "type": "team", "parent": {"name": "weird", "type": "bogus"}}
        },
    },
    "indexes": {
        "membership": {"membership_index": {"euser": [{"name": "t", "type": "team"}]}},
        "slack_id_mappings": {"slack_uid_to_uid": {"Suser": "euser"}},
    },
}


# Direct org membership listed BEFORE a team under it: P(org) <- O(org) <- T(team).
# The team walk must continue past the already-seen O to reach P.
ORDERING_INDEX = {
    "metadata": {},
    "lookups": {
        "employees": {"euser": {"uid": "euser"}},
        "orgs": {
            "P": {"name": "P", "type": "org", "stable_id": "p1"},
            "O": {
                "name": "O",
                "type": "org",
                "stable_id": "o1",
                "parent": {"name": "P", "type": "org"},
                "parent_id": "p1",
            },
        },
        "teams": {
            "T": {
                "name": "T",
                "type": "team",
                "stable_id": "t1",
                "parent": {"name": "O", "type": "org"},
                "parent_id": "o1",
            }
        },
    },
    "indexes": {
        "membership": {
            "membership_index": {
                "euser": [
                    {"name": "O", "type": "org", "stable_id": "o1"},
                    {"name": "T", "type": "team", "stable_id": "t1"},
                ]
            }
        },
        "slack_id_mappings": {"slack_uid_to_uid": {"Suser": "euser"}},
    },
}

# Cyclic parent links A <-> B, with team T under A. Traversal must terminate.
CYCLE_INDEX = {
    "metadata": {},
    "lookups": {
        "employees": {"euser": {"uid": "euser"}},
        "orgs": {
            "A": {"name": "A", "type": "org", "stable_id": "a1", "parent": {"name": "B", "type": "org"}, "parent_id": "b1"},
            "B": {"name": "B", "type": "org", "stable_id": "b1", "parent": {"name": "A", "type": "org"}, "parent_id": "a1"},
        },
        "teams": {
            "T": {"name": "T", "type": "team", "stable_id": "t1", "parent": {"name": "A", "type": "org"}, "parent_id": "a1"},
        },
    },
    "indexes": {
        "membership": {"membership_index": {"euser": [{"name": "T", "type": "team", "stable_id": "t1"}]}},
        "slack_id_mappings": {"slack_uid_to_uid": {"Suser": "euser"}},
    },
}


class TestStableIdAncestryTraversal:
    def test_sync_org_before_team_keeps_higher_ancestors(self):
        svc = Service()
        svc.load_from_data_source(_DictSource(ORDERING_INDEX))
        assert svc._use_stable_ids is True
        got = {(o.name, str(o.type)) for o in svc.get_user_organizations("Suser")}
        assert ("O", "Organization") in got
        assert ("T", "Team") in got
        assert ("P", "Organization") in got  # not dropped despite O being seen first

    @pytest.mark.asyncio
    async def test_async_org_before_team_keeps_higher_ancestors(self):
        svc = AsyncService()
        await svc.load_from_data_source(_AsyncDictSource(ORDERING_INDEX))
        got = {(o.name, str(o.type)) for o in await svc.get_user_organizations("Suser")}
        assert ("P", "Organization") in got

    def test_sync_cyclic_parents_terminate(self):
        svc = Service()
        svc.load_from_data_source(_DictSource(CYCLE_INDEX))
        got = {o.name for o in svc.get_user_organizations("Suser")}
        assert {"T", "A", "B"} <= got  # terminates and includes the cycle members

    @pytest.mark.asyncio
    async def test_async_cyclic_parents_terminate(self):
        svc = AsyncService()
        await svc.load_from_data_source(_AsyncDictSource(CYCLE_INDEX))
        got = {o.name for o in await svc.get_user_organizations("Suser")}
        assert {"T", "A", "B"} <= got


class TestUnknownParentTypeIsSkipped:
    def test_sync_does_not_raise_on_unknown_type(self):
        svc = Service()
        svc.load_from_data_source(_DictSource(BOGUS_PARENT_INDEX))
        assert svc._use_stable_ids is False
        orgs = svc.get_user_organizations("Suser")
        # The bogus-typed ancestor is skipped; the team itself is returned.
        assert [(o.name, o.type) for o in orgs] == [("t", OrgInfoType.TEAM)]

    @pytest.mark.asyncio
    async def test_async_does_not_raise_on_unknown_type(self):
        svc = AsyncService()
        await svc.load_from_data_source(_AsyncDictSource(BOGUS_PARENT_INDEX))
        assert svc._use_stable_ids is False
        orgs = await svc.get_user_organizations("Suser")
        assert [(o.name, o.type) for o in orgs] == [("t", OrgInfoType.TEAM)]


class TestSyncBackwardCompat:
    def test_legacy_index_uses_fallback(self):
        svc = Service()
        svc.load_from_data_source(_DictSource(LEGACY_INDEX))
        assert svc._use_stable_ids is False
        path = svc.get_hierarchy_path("t", "team")
        assert [(e.name, e.type) for e in path] == [
            ("t", "team"),
            ("grp", "team_group"),
            ("acme", "org"),
        ]

    @pytest.mark.parametrize("index", [DUPLICATE_ID_INDEX, DANGLING_PARENT_INDEX])
    def test_malformed_stable_index_falls_back(self, index: dict):
        svc = Service()
        svc.load_from_data_source(_DictSource(index))
        assert svc._use_stable_ids is False


class TestAsyncStableIDCollision:
    @pytest.mark.asyncio
    async def test_async_matches_sync(self):
        svc = AsyncService()
        await svc.load_from_data_source(_AsyncDictSource(COLLISION_INDEX))
        assert svc._use_stable_ids is True

        for typ, expected in [
            ("team_group", [("shared", "team_group", "g1"), ("acme", "org", "o1")]),
            (
                "team",
                [
                    ("shared", "team", "t1"),
                    ("shared", "team_group", "g1"),
                    ("acme", "org", "o1"),
                ],
            ),
        ]:
            path = await svc.get_hierarchy_path("shared", typ)
            assert [(e.name, e.type, e.stable_id) for e in path] == expected

        orgs = await svc.get_user_organizations("Suser")
        assert [(o.name, o.type, o.stable_id) for o in orgs] == [
            ("shared", OrgInfoType.TEAM, "t1"),
            ("shared", OrgInfoType.TEAM_GROUP, "g1"),
            ("acme", OrgInfoType.ORGANIZATION, "o1"),
        ]

        tree = await svc.get_descendants_tree("acme")
        assert tree is not None
        assert tree.children[0].stable_id == "g1"
        assert tree.children[0].children[0].stable_id == "t1"
