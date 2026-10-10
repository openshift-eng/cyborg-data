"""Fake GCS client implementation for testing.

This module provides fake implementations of the google.cloud.storage
Client, Bucket, and Blob classes for testing GCS-related code without
requiring actual GCS connections.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import BinaryIO

from ..._types import DataVersionRef


class FakeBucket:
    """Fake implementation of google.cloud.storage.Bucket."""

    def __init__(self, name: str, client: FakeGCSClient | None = None) -> None:
        self.name = name
        self.client = client
        self.blobs: dict[str, dict] = {}
        # name -> list of all retained generations, oldest first (emulates
        # object versioning).
        self.history: dict[str, list[dict]] = {}

    def blob(self, name: str) -> FakeBlob:
        """Get a blob reference."""
        return FakeBlob(name, self)

    def get_blob_data(self, name: str) -> dict | None:
        """Get blob data from internal storage."""
        return self.blobs.get(name)

    def set_blob_data(self, name: str, data: dict) -> None:
        """Set blob data in internal storage."""
        self.blobs[name] = data
        self.history.setdefault(name, []).append(data)

    def add_blob(
        self,
        name: str,
        content: bytes,
        generation: int = 1,
        updated: datetime | None = None,
    ) -> None:
        """Add a blob with content for testing."""
        data = {
            "content": content,
            "generation": generation,
            "updated": updated or datetime.now(),
        }
        self.blobs[name] = data
        self.history[name] = [data]

    def update_blob(
        self, name: str, content: bytes, updated: datetime | None = None
    ) -> None:
        """Write a new generation of a blob, retaining prior ones."""
        if name not in self.blobs:
            self.add_blob(name, content, updated=updated)
            return
        current = self.blobs[name]
        data = {
            "content": content,
            "generation": current["generation"] + 1,
            "updated": updated or datetime.now(),
        }
        self.blobs[name] = data
        self.history.setdefault(name, []).append(data)

    def versions(self, name: str) -> list[dict]:
        """Return all retained generations of a blob, oldest first."""
        return list(self.history.get(name, []))

    def get_generation_data(self, name: str, generation: int) -> dict | None:
        """Return a specific retained generation of a blob."""
        for data in self.history.get(name, []):
            if data["generation"] == generation:
                return data
        return None


class FakeBlob:
    """Fake implementation of google.cloud.storage.Blob."""

    def __init__(self, name: str, bucket: FakeBucket) -> None:
        self.name = name
        self.bucket = bucket
        self._generation = 1
        self._updated = datetime.now()

    @property
    def generation(self) -> int:
        """Return the generation number of the blob."""
        return self._generation

    @property
    def updated(self) -> datetime:
        """Return when the blob was last updated."""
        return self._updated

    def reload(self) -> None:
        """Reload blob metadata from the fake storage."""
        data = self.bucket.get_blob_data(self.name)
        if data is None:
            raise Exception(f"Blob {self.name} not found")
        self._generation = data["generation"]
        self._updated = data["updated"]

    def download_as_bytes(self) -> bytes:
        """Download the blob content as bytes."""
        data = self.bucket.get_blob_data(self.name)
        if data is None:
            raise Exception(f"Blob {self.name} not found")
        return data["content"]

    def upload_from_string(self, content: str | bytes) -> None:
        """Upload content to the blob."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.bucket.set_blob_data(
            self.name,
            {
                "content": content,
                "generation": self._generation + 1,
                "updated": datetime.now(),
            },
        )
        self._generation += 1
        self._updated = datetime.now()


class FakeGCSClient:
    """Fake implementation of google.cloud.storage.Client."""

    def __init__(self, project: str | None = None) -> None:
        self.project = project
        self.buckets: dict[str, FakeBucket] = {}

    @classmethod
    def from_service_account_json(cls, json_path: str) -> FakeGCSClient:
        """Create a client from a service account JSON file (fake)."""
        return cls(project="fake-project-from-json")

    def bucket(self, name: str) -> FakeBucket:
        """Get a bucket reference."""
        if name not in self.buckets:
            self.buckets[name] = FakeBucket(name, self)
        return self.buckets[name]

    def add_bucket(self, name: str) -> FakeBucket:
        """Add a bucket for testing."""
        bucket = FakeBucket(name, self)
        self.buckets[name] = bucket
        return bucket


class FakeGCSDataSource:
    """A fake GCS data source that uses in-memory storage.

    This can be used directly in tests as a DataSource implementation.
    """

    def __init__(
        self,
        bucket: str,
        object_path: str,
        content: bytes | str = b"{}",
        created: datetime | None = None,
    ) -> None:
        self.bucket_name = bucket
        self.object_path = object_path
        self._client = FakeGCSClient()
        self._bucket = self._client.add_bucket(bucket)

        if isinstance(content, str):
            content = content.encode("utf-8")
        self._bucket.add_blob(object_path, content, updated=created)

        self._generation = 1
        self._stop_watching = False

    def load(self) -> BinaryIO:
        """Load data from fake GCS."""
        blob = self._bucket.blob(self.object_path)
        content = blob.download_as_bytes()
        return BytesIO(content)

    def watch(self, callback) -> Exception | None:
        """Watch for changes (no-op in fake implementation)."""
        return None

    def update_content(self, content: bytes | str) -> None:
        """Update the blob content (for testing hot reload)."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        self._bucket.update_blob(self.object_path, content)
        self._generation += 1

    def add_version_at(self, content: bytes | str, created: datetime) -> None:
        """Append a new generation with an explicit creation time.

        Builds deterministic version histories for time-travel tests.
        """
        if isinstance(content, str):
            content = content.encode("utf-8")
        self._bucket.update_blob(self.object_path, content, updated=created)
        self._generation += 1

    def list_versions(self) -> list[DataVersionRef]:
        """Return all retained generations as version refs (HistoricalDataSource)."""
        return [
            DataVersionRef(id=str(data["generation"]), created=data["updated"])
            for data in self._bucket.versions(self.object_path)
        ]

    def load_version(self, ref: DataVersionRef) -> BinaryIO:
        """Return a reader for a specific generation (HistoricalDataSource)."""
        data = self._bucket.get_generation_data(self.object_path, int(ref.id))
        if data is None:
            raise Exception(f"generation {ref.id} not found for {self.object_path}")
        return BytesIO(data["content"])

    def __str__(self) -> str:
        return f"gs://{self.bucket_name}/{self.object_path} (fake)"
