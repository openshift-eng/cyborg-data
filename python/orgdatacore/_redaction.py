"""Data source wrapper for PII redaction."""

import json
from dataclasses import replace
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO

from ._serialization import data_to_json_bytes
from ._service import parse_data
from ._types import (
    Data,
    DataSource,
    GitHubIDMappings,
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

    def watch(
        self, callback: "Callable[[], Exception | None]"
    ) -> Exception | None:
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


def _redact(data: Data) -> Data:
    """Return a new Data with PII fields redacted."""
    new_employees = {
        uid: replace(
            emp,
            full_name="[REDACTED]",
            email="[REDACTED]",
            slack_uid="",
            github_id="",
        )
        for uid, emp in data.lookups.employees.items()
    }
    return replace(
        data,
        lookups=replace(data.lookups, employees=new_employees),
        indexes=replace(
            data.indexes,
            slack_id_mappings=SlackIDMappings(slack_uid_to_uid={}),
            github_id_mappings=GitHubIDMappings(github_id_to_uid={}),
        ),
    )
