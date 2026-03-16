"""Data source wrappers for PII redaction."""

import json
from io import BytesIO
from typing import TYPE_CHECKING, Any, BinaryIO

from ._serialization import data_to_json_bytes
from ._service import parse_data
from ._types import (
    Data,
    DataSource,
    GitHubIDMappings,
    Group,
    PIIMode,
    SlackIDMappings,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class RedactingDataSource:
    """
    DataSource decorator that redacts PII from loaded data.

    When pii_mode is REDACTED, this wrapper intercepts the JSON stream
    from the inner data source and strips PII fields before the data
    is parsed by Service, so PII is not propagated to downstream consumers.

    PII fields redacted:
    - full_name -> "[REDACTED]"
    - email -> "[REDACTED]"
    - slack_uid -> "" (omitted from JSON)
    - github_id -> "" (omitted from JSON)

    PII indexes cleared:
    - slack_id_mappings.slack_uid_to_uid
    - github_id_mappings.github_id_to_uid
    """

    def __init__(
        self,
        source: DataSource,
        pii_mode: PIIMode = PIIMode.FULL,
    ) -> None:
        """
        Initialize the redacting data source.

        Args:
            source: The underlying data source to wrap.
            pii_mode: The PII handling mode. Defaults to FULL (no redaction).
        """
        if pii_mode not in (PIIMode.FULL, PIIMode.REDACTED):
            raise ValueError(
                f"RedactingDataSource only supports FULL and REDACTED modes, got {pii_mode!r}"
            )
        self._source = source
        self._pii_mode = pii_mode

    def load(self) -> BinaryIO:
        """
        Load data, optionally redacting PII fields.

        Returns:
            Binary stream containing the (possibly redacted) JSON data.
        """
        reader = self._source.load()

        if self._pii_mode == PIIMode.FULL:
            return reader  # Pass through unchanged

        # Parse, redact, re-serialize
        try:
            raw = json.load(reader)
        finally:
            reader.close()
        data = parse_data(raw)
        redacted = _redact(data)
        return BytesIO(data_to_json_bytes(redacted))

    def watch(self, callback: "Callable[[], Exception | None]") -> Exception | None:
        """
        Monitor for changes and call the callback when data is updated.

        Delegates to the underlying data source.

        Args:
            callback: Function to call when data changes.

        Returns:
            Exception if watch setup failed, None otherwise.
        """
        return self._source.watch(callback)

    def __str__(self) -> str:
        """Return a description of this data source."""
        mode_suffix = " [PII redacted]" if self._pii_mode == PIIMode.REDACTED else ""
        return f"{self._source}{mode_suffix}"


class AsyncRedactingDataSource:
    """Async DataSource decorator that redacts PII from loaded data.

    Same redaction as RedactingDataSource but with async load().
    Use with AsyncService and async inner sources.
    """

    def __init__(
        self,
        source: Any,
        pii_mode: PIIMode = PIIMode.FULL,
    ) -> None:
        if pii_mode not in (PIIMode.FULL, PIIMode.REDACTED):
            raise ValueError(
                f"AsyncRedactingDataSource only supports FULL and REDACTED modes, got {pii_mode!r}"
            )
        self._source = source
        self._pii_mode = pii_mode

    async def load(self) -> BinaryIO:
        """Load data asynchronously, optionally redacting PII fields."""
        reader: BinaryIO = await self._source.load()

        if self._pii_mode == PIIMode.FULL:
            return reader

        try:
            raw = reader.read()
        finally:
            reader.close()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        raw_data = json.loads(text)
        data = parse_data(raw_data)
        redacted = _redact(data)
        return BytesIO(data_to_json_bytes(redacted))

    async def watch(self, callback: Any) -> Any:
        """Delegate to the underlying data source."""
        return await self._source.watch(callback)

    def __str__(self) -> str:
        mode_suffix = " [PII redacted]" if self._pii_mode == PIIMode.REDACTED else ""
        return f"{self._source}{mode_suffix}"


def _redact(data: Data) -> Data:
    """Return a new Data with PII fields redacted."""
    new_employees = {
        uid: emp.model_copy(
            update={
                "full_name": "[REDACTED]",
                "email": "[REDACTED]",
                "slack_uid": "",
                "github_id": "",
            }
        )
        for uid, emp in data.lookups.employees.items()
    }

    new_teams = {
        name: team.model_copy(update={"group": _redact_group(team.group)})
        for name, team in data.lookups.teams.items()
    }
    new_orgs = {
        name: org.model_copy(update={"group": _redact_group(org.group)})
        for name, org in data.lookups.orgs.items()
    }
    new_pillars = {
        name: pillar.model_copy(update={"group": _redact_group(pillar.group)})
        for name, pillar in data.lookups.pillars.items()
    }
    new_team_groups = {
        name: tg.model_copy(update={"group": _redact_group(tg.group)})
        for name, tg in data.lookups.team_groups.items()
    }

    return data.model_copy(
        update={
            "lookups": data.lookups.model_copy(
                update={
                    "employees": new_employees,
                    "teams": new_teams,
                    "orgs": new_orgs,
                    "pillars": new_pillars,
                    "team_groups": new_team_groups,
                }
            ),
            "indexes": data.indexes.model_copy(
                update={
                    "slack_id_mappings": SlackIDMappings(slack_uid_to_uid={}),
                    "github_id_mappings": GitHubIDMappings(github_id_to_uid={}),
                }
            ),
        }
    )


def _redact_group(group: Group) -> Group:
    """Return a new Group with escalation contacts redacted."""
    if not group.escalation:
        return group
    new_escalation = tuple(
        contact.model_copy(
            update={"name": "[REDACTED]", "url": "", "description": "[REDACTED]"}
        )
        for contact in group.escalation
    )
    return group.model_copy(update={"escalation": new_escalation})
