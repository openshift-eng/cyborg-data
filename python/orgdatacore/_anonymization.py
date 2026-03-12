"""Data source wrappers for PII anonymization.

Replaces real UIDs with random nonces (HUMAN-<hex>) while preserving
structural relationships, allowing AI to reason about people without
seeing real identities. Nonce mappings are stable across reloads —
existing UIDs keep their nonces, new UIDs get fresh random nonces.
"""

import json
import secrets
from dataclasses import replace
from io import BytesIO
from typing import TYPE_CHECKING, Any, BinaryIO

from ._serialization import data_to_json_bytes
from ._service import parse_data
from ._types import (
    Data,
    GitHubIDMappings,
    Group,
    MembershipIndex,
    PIIMode,
    SlackIDMappings,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class _AnonymizationEngine:
    """Shared anonymization logic for sync and async data sources.

    Builds UID-to-nonce lookup tables and rewrites org data JSON
    to replace real identifiers with anonymized nonces.
    """

    def __init__(self) -> None:
        self._nonce_to_uid: dict[str, str] = {}
        self._uid_to_nonce: dict[str, str] = {}
        self._name_to_nonce: dict[str, str] = {}
        self._nonce_to_display: dict[str, str] = {}
        self._slack_id_to_nonce: dict[str, str] = {}
        self._github_id_to_nonce: dict[str, str] = {}

    @property
    def uid_to_nonce_map(self) -> dict[str, str]:
        """Read-only map of real UID -> nonce."""
        return dict(self._uid_to_nonce)

    @property
    def name_to_nonce_map(self) -> dict[str, str]:
        """Read-only map of lowered full name -> nonce."""
        return dict(self._name_to_nonce)

    @property
    def slack_id_to_nonce_map(self) -> dict[str, str]:
        """Read-only map of Slack user ID -> nonce."""
        return dict(self._slack_id_to_nonce)

    @property
    def github_id_to_nonce_map(self) -> dict[str, str]:
        """Read-only map of GitHub ID -> nonce."""
        return dict(self._github_id_to_nonce)

    def resolve(self, nonce: str) -> str | None:
        """Resolve a nonce back to a real UID."""
        return self._nonce_to_uid.get(nonce)

    def anonymize_uid(self, uid: str) -> str | None:
        """Map a real UID to its nonce."""
        return self._uid_to_nonce.get(uid)

    def lookup_by_name(self, name: str) -> str | None:
        """Case-insensitive name lookup returning the nonce."""
        return self._name_to_nonce.get(name.lower())

    def get_display_name(self, nonce: str) -> str | None:
        """Get human-readable display for a nonce: 'Full Name (uid)'."""
        return self._nonce_to_display.get(nonce)

    def _generate_nonce(self, prefix: str, used: set[str]) -> str:
        """Generate a unique <prefix><hex> nonce."""
        while True:
            nonce = f"{prefix}{secrets.token_hex(4)}"
            if nonce not in used:
                used.add(nonce)
                return nonce

    def anonymize(self, data: Data) -> Data:
        """Anonymize org data and rebuild lookup tables. Returns new Data."""
        employees = data.lookups.employees

        # Preserve existing UID->nonce mappings for UIDs that still exist;
        # generate new random nonces only for new employees.
        prev_uid_to_nonce = self._uid_to_nonce

        self._nonce_to_uid = {}
        self._uid_to_nonce = {}
        self._name_to_nonce = {}
        self._nonce_to_display = {}
        self._slack_id_to_nonce = {}
        self._github_id_to_nonce = {}

        used_nonces: set[str] = set(
            prev_uid_to_nonce[uid]
            for uid in employees
            if uid in prev_uid_to_nonce
        )

        # Phase 1: Build UID -> nonce mapping for all employees
        for uid, emp in employees.items():
            # Reuse existing nonce if available, otherwise generate new one
            nonce = prev_uid_to_nonce.get(uid) or self._generate_nonce("HUMAN-", used_nonces)
            self._uid_to_nonce[uid] = nonce
            self._nonce_to_uid[nonce] = uid

            if emp.full_name:
                self._name_to_nonce[emp.full_name.lower()] = nonce
                self._nonce_to_display[nonce] = emp.full_name
            else:
                self._nonce_to_display[nonce] = nonce

        # Phase 2: Build Slack ID and GitHub ID nonce mappings.
        # First try the indexes, then fall back to employee records
        # (the indexes may be empty if the data dump didn't populate them).
        slack_uid_to_uid = dict(data.indexes.slack_id_mappings.slack_uid_to_uid)
        github_id_to_uid = dict(data.indexes.github_id_mappings.github_id_to_uid)

        # Fill from employee records if indexes are incomplete
        for uid, emp in employees.items():
            if emp.slack_uid and emp.slack_uid not in slack_uid_to_uid:
                slack_uid_to_uid[emp.slack_uid] = uid
            if emp.github_id and emp.github_id not in github_id_to_uid:
                github_id_to_uid[emp.github_id] = uid

        for slack_id, uid in slack_uid_to_uid.items():
            if uid in self._uid_to_nonce:
                slack_nonce = self._generate_nonce("SLACK-", used_nonces)
                self._slack_id_to_nonce[slack_id] = slack_nonce
                self._nonce_to_display[slack_nonce] = slack_id
        for github_id, uid in github_id_to_uid.items():
            if uid in self._uid_to_nonce:
                github_nonce = self._generate_nonce("GITHUB-", used_nonces)
                self._github_id_to_nonce[github_id] = github_nonce
                self._nonce_to_display[github_nonce] = github_id

        # Build reverse maps: uid -> slack nonce, uid -> github nonce
        uid_to_slack_nonce: dict[str, str] = {}
        for slack_id, uid in slack_uid_to_uid.items():
            if slack_id in self._slack_id_to_nonce:
                uid_to_slack_nonce[uid] = self._slack_id_to_nonce[slack_id]
        uid_to_github_nonce: dict[str, str] = {}
        for github_id, uid in github_id_to_uid.items():
            if github_id in self._github_id_to_nonce:
                uid_to_github_nonce[uid] = self._github_id_to_nonce[github_id]

        # Phase 3: Rewrite employee records
        new_employees: dict[str, Any] = {}
        for uid, emp in employees.items():
            nonce = self._uid_to_nonce[uid]

            manager_nonce = ""
            if emp.manager_uid:
                manager_nonce = self._uid_to_nonce.get(emp.manager_uid, "")

            new_employees[nonce] = replace(
                emp,
                uid=nonce,
                full_name="[ANONYMIZED]",
                email="[ANONYMIZED]",
                slack_uid=uid_to_slack_nonce.get(uid, ""),
                github_id=uid_to_github_nonce.get(uid, ""),
                manager_uid=manager_nonce,
            )

        # Phase 4: Rewrite indexes
        # Re-key membership index
        new_membership_index: dict[str, Any] = {}
        for uid, memberships in data.indexes.membership.membership_index.items():
            mapped_nonce = self._uid_to_nonce.get(uid)
            if mapped_nonce:
                new_membership_index[mapped_nonce] = memberships

        # Remap slack index: slack_nonce -> uid_nonce
        new_slack_index: dict[str, str] = {}
        for slack_id, slack_nonce in self._slack_id_to_nonce.items():
            uid_nonce = self._uid_to_nonce.get(slack_uid_to_uid.get(slack_id, ""), "")
            if uid_nonce:
                new_slack_index[slack_nonce] = uid_nonce

        # Remap github index: github_nonce -> uid_nonce
        new_github_index: dict[str, str] = {}
        for github_id, github_nonce in self._github_id_to_nonce.items():
            uid_nonce = self._uid_to_nonce.get(github_id_to_uid.get(github_id, ""), "")
            if uid_nonce:
                new_github_index[github_nonce] = uid_nonce

        # Phase 5: Rewrite group people lists in teams/orgs/pillars/team_groups
        new_teams = {
            name: replace(t, group=_remap_group(t.group, self._uid_to_nonce))
            for name, t in data.lookups.teams.items()
        }
        new_orgs = {
            name: replace(o, group=_remap_group(o.group, self._uid_to_nonce))
            for name, o in data.lookups.orgs.items()
        }
        new_pillars = {
            name: replace(p, group=_remap_group(p.group, self._uid_to_nonce))
            for name, p in data.lookups.pillars.items()
        }
        new_team_groups = {
            name: replace(tg, group=_remap_group(tg.group, self._uid_to_nonce))
            for name, tg in data.lookups.team_groups.items()
        }

        return replace(
            data,
            lookups=replace(
                data.lookups,
                employees=new_employees,
                teams=new_teams,
                orgs=new_orgs,
                pillars=new_pillars,
                team_groups=new_team_groups,
            ),
            indexes=replace(
                data.indexes,
                membership=MembershipIndex(membership_index=new_membership_index),
                slack_id_mappings=SlackIDMappings(slack_uid_to_uid=new_slack_index),
                github_id_mappings=GitHubIDMappings(github_id_to_uid=new_github_index),
            ),
        )


def _remap_group(group: Group, uid_to_nonce: dict[str, str]) -> Group:
    """Return a new Group with people UIDs replaced by nonces."""
    new_people = tuple(
        uid_to_nonce.get(uid, uid) for uid in group.resolved_people_uid_list
    )
    new_roles = tuple(
        replace(
            role,
            people=tuple(uid_to_nonce.get(uid, uid) for uid in role.people),
        )
        for role in group.roles
    ) if group.roles else ()
    return replace(group, resolved_people_uid_list=new_people, roles=new_roles)


class AnonymizingDataSource:
    """DataSource decorator that anonymizes PII in loaded data.

    When pii_mode is ANONYMIZED, replaces UIDs with random nonces
    and strips PII fields, while preserving structural relationships.
    Nonce tables are rebuilt on every load() call (ephemeral).

    PII fields anonymized:
    - uid -> HUMAN-<hex> nonce
    - full_name -> "[ANONYMIZED]"
    - email -> "[ANONYMIZED]"
    - slack_uid -> SLACK-<hex> nonce
    - github_id -> GITHUB-<hex> nonce
    - manager_uid -> mapped HUMAN nonce (consistent)

    Indexes re-mapped:
    - membership_index keys -> HUMAN nonces
    - resolved_people_uid_list -> HUMAN nonces
    - roles.people -> HUMAN nonces
    - slack_id_mappings: SLACK nonce -> HUMAN nonce
    - github_id_mappings: GITHUB nonce -> HUMAN nonce
    """

    def __init__(
        self,
        source: Any,
        pii_mode: PIIMode = PIIMode.FULL,
    ) -> None:
        self._source = source
        self._pii_mode = pii_mode
        self._engine = _AnonymizationEngine()

    def load(self) -> BinaryIO:
        """Load data, optionally anonymizing PII fields."""
        reader: BinaryIO = self._source.load()

        if self._pii_mode != PIIMode.ANONYMIZED:
            return reader

        try:
            raw = json.load(reader)
        finally:
            reader.close()
        data = parse_data(raw)
        anonymized = self._engine.anonymize(data)
        return BytesIO(data_to_json_bytes(anonymized))

    def watch(
        self, callback: "Callable[[], Exception | None]"
    ) -> Exception | None:
        """Delegate to the underlying data source."""
        result: Exception | None = self._source.watch(callback)
        return result

    def __str__(self) -> str:
        mode_suffix = (
            " [PII anonymized]" if self._pii_mode == PIIMode.ANONYMIZED else ""
        )
        return f"{self._source}{mode_suffix}"

    # Public API — delegates to engine
    def resolve(self, nonce: str) -> str | None:
        return self._engine.resolve(nonce)

    def anonymize_uid(self, uid: str) -> str | None:
        return self._engine.anonymize_uid(uid)

    def lookup_by_name(self, name: str) -> str | None:
        return self._engine.lookup_by_name(name)

    def get_display_name(self, nonce: str) -> str | None:
        return self._engine.get_display_name(nonce)

    @property
    def uid_to_nonce_map(self) -> dict[str, str]:
        return self._engine.uid_to_nonce_map

    @property
    def name_to_nonce_map(self) -> dict[str, str]:
        return self._engine.name_to_nonce_map

    @property
    def slack_id_to_nonce_map(self) -> dict[str, str]:
        return self._engine.slack_id_to_nonce_map

    @property
    def github_id_to_nonce_map(self) -> dict[str, str]:
        return self._engine.github_id_to_nonce_map


class AsyncAnonymizingDataSource:
    """Async DataSource decorator that anonymizes PII in loaded data.

    Same anonymization as AnonymizingDataSource but with async load().
    Use with AsyncService and async inner sources (AsyncFileDataSource,
    AsyncGCSDataSource).
    """

    def __init__(
        self,
        source: Any,
        pii_mode: PIIMode = PIIMode.FULL,
    ) -> None:
        self._source = source
        self._pii_mode = pii_mode
        self._engine = _AnonymizationEngine()

    async def load(self) -> BinaryIO:
        """Load data asynchronously, optionally anonymizing PII fields."""
        reader: BinaryIO = await self._source.load()

        if self._pii_mode != PIIMode.ANONYMIZED:
            return reader

        try:
            raw = reader.read()
        finally:
            reader.close()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        raw_data = json.loads(text)
        data = parse_data(raw_data)
        anonymized = self._engine.anonymize(data)
        return BytesIO(data_to_json_bytes(anonymized))

    async def watch(self, callback: Any) -> Any:
        """Delegate to the underlying data source."""
        return await self._source.watch(callback)

    def __str__(self) -> str:
        mode_suffix = (
            " [PII anonymized]" if self._pii_mode == PIIMode.ANONYMIZED else ""
        )
        return f"{self._source}{mode_suffix}"

    # Public API — delegates to engine
    def resolve(self, nonce: str) -> str | None:
        return self._engine.resolve(nonce)

    def anonymize_uid(self, uid: str) -> str | None:
        return self._engine.anonymize_uid(uid)

    def lookup_by_name(self, name: str) -> str | None:
        return self._engine.lookup_by_name(name)

    def get_display_name(self, nonce: str) -> str | None:
        return self._engine.get_display_name(nonce)

    @property
    def uid_to_nonce_map(self) -> dict[str, str]:
        return self._engine.uid_to_nonce_map

    @property
    def name_to_nonce_map(self) -> dict[str, str]:
        return self._engine.name_to_nonce_map

    @property
    def slack_id_to_nonce_map(self) -> dict[str, str]:
        return self._engine.slack_id_to_nonce_map

    @property
    def github_id_to_nonce_map(self) -> dict[str, str]:
        return self._engine.github_id_to_nonce_map
