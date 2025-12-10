"""Tests for GCS data source functionality using fake implementations."""

import pytest

from orgdatacore import Service
from orgdatacore._exceptions import GCSError
from orgdatacore._gcs import GCSDataSource, _retry_with_backoff
from orgdatacore._internal.testing import (
    FakeGCSClient,
    FakeGCSDataSource,
    create_test_data_json,
)
from orgdatacore._types import GCSConfig


class TestGCSDataSourceStub:
    """Tests for the GCS stub implementation (when SDK is not available)."""

    def test_stub_load_raises_error(self) -> None:
        """Test that stub implementation raises GCSError on load."""
        config = GCSConfig(bucket="test-bucket", object_path="test/path.json")
        source = GCSDataSource(config)

        with pytest.raises(GCSError, match="GCS support not enabled"):
            source.load()

    def test_stub_watch_returns_error(self) -> None:
        """Test that stub implementation returns error on watch."""
        config = GCSConfig(bucket="test-bucket", object_path="test/path.json")
        source = GCSDataSource(config)

        result = source.watch(lambda: None)
        assert isinstance(result, GCSError)

    def test_stub_str(self) -> None:
        """Test stub string representation."""
        config = GCSConfig(bucket="my-bucket", object_path="data/file.json")
        source = GCSDataSource(config)

        assert "gs://my-bucket/data/file.json" in str(source)
        assert "stub" in str(source)


class TestFakeGCSClient:
    """Tests for the fake GCS client implementation."""

    def test_create_client(self) -> None:
        """Test creating a fake GCS client."""
        client = FakeGCSClient(project="test-project")
        assert client.project == "test-project"

    def test_from_service_account_json(self) -> None:
        """Test creating client from service account JSON."""
        client = FakeGCSClient.from_service_account_json("/path/to/key.json")
        assert client.project == "fake-project-from-json"

    def test_bucket_creation(self) -> None:
        """Test getting a bucket reference."""
        client = FakeGCSClient()
        bucket = client.bucket("my-bucket")
        assert bucket.name == "my-bucket"

    def test_bucket_caching(self) -> None:
        """Test that bucket references are cached."""
        client = FakeGCSClient()
        bucket1 = client.bucket("my-bucket")
        bucket2 = client.bucket("my-bucket")
        assert bucket1 is bucket2

    def test_add_bucket(self) -> None:
        """Test adding a bucket."""
        client = FakeGCSClient()
        bucket = client.add_bucket("new-bucket")
        assert bucket.name == "new-bucket"
        assert client.bucket("new-bucket") is bucket


class TestFakeBucket:
    """Tests for the fake bucket implementation."""

    def test_blob_creation(self) -> None:
        """Test creating a blob reference."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        blob = bucket.blob("path/to/file.json")
        assert blob.name == "path/to/file.json"

    def test_add_blob(self) -> None:
        """Test adding a blob with content."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        bucket.add_blob("test.json", b'{"key": "value"}')

        blob = bucket.blob("test.json")
        assert blob.download_as_bytes() == b'{"key": "value"}'

    def test_update_blob(self) -> None:
        """Test updating blob content."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        bucket.add_blob("test.json", b"original", generation=1)

        bucket.update_blob("test.json", b"updated")

        blob = bucket.blob("test.json")
        blob.reload()
        assert blob.download_as_bytes() == b"updated"
        assert blob.generation == 2


class TestFakeBlob:
    """Tests for the fake blob implementation."""

    def test_download_as_bytes(self) -> None:
        """Test downloading blob content."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        bucket.add_blob("test.json", b"test content")

        blob = bucket.blob("test.json")
        content = blob.download_as_bytes()
        assert content == b"test content"

    def test_download_nonexistent_raises(self) -> None:
        """Test that downloading nonexistent blob raises exception."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        blob = bucket.blob("nonexistent.json")

        with pytest.raises(Exception, match="not found"):
            blob.download_as_bytes()

    def test_reload(self) -> None:
        """Test reloading blob metadata."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        bucket.add_blob("test.json", b"content", generation=5)

        blob = bucket.blob("test.json")
        blob.reload()
        assert blob.generation == 5

    def test_reload_nonexistent_raises(self) -> None:
        """Test that reloading nonexistent blob raises exception."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        blob = bucket.blob("nonexistent.json")

        with pytest.raises(Exception, match="not found"):
            blob.reload()

    def test_upload_from_string(self) -> None:
        """Test uploading content to blob."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        bucket.add_blob("test.json", b"original")

        blob = bucket.blob("test.json")
        blob.upload_from_string("new content")

        assert blob.download_as_bytes() == b"new content"

    def test_generation_increments_on_update(self) -> None:
        """Test that generation increments when blob is updated."""
        client = FakeGCSClient()
        bucket = client.add_bucket("test-bucket")
        bucket.add_blob("test.json", b"v1", generation=1)

        blob = bucket.blob("test.json")
        blob.reload()
        initial_gen = blob.generation

        bucket.update_blob("test.json", b"v2")
        blob.reload()

        assert blob.generation == initial_gen + 1


class TestFakeGCSDataSource:
    """Tests for the fake GCS data source."""

    def test_load(self) -> None:
        """Test loading data from fake GCS."""
        source = FakeGCSDataSource(
            bucket="test-bucket",
            object_path="data.json",
            content=create_test_data_json(),
        )

        reader = source.load()
        content = reader.read()
        assert b"testuser1" in content

    def test_str(self) -> None:
        """Test string representation."""
        source = FakeGCSDataSource(
            bucket="my-bucket",
            object_path="path/to/data.json",
            content="{}",
        )
        assert "gs://my-bucket/path/to/data.json" in str(source)

    def test_update_content(self) -> None:
        """Test updating content for hot reload testing."""
        source = FakeGCSDataSource(
            bucket="test-bucket",
            object_path="data.json",
            content=b'{"version": 1}',
        )

        # Initial load
        reader = source.load()
        assert b'"version": 1' in reader.read()

        # Update content
        source.update_content(b'{"version": 2}')

        # Load updated content
        reader = source.load()
        assert b'"version": 2' in reader.read()


class TestFakeGCSWithService:
    """Integration tests using fake GCS with the Service."""

    def test_service_load_from_fake_gcs(self) -> None:
        """Test loading service data from fake GCS."""
        source = FakeGCSDataSource(
            bucket="org-data",
            object_path="comprehensive_index_dump.json",
            content=create_test_data_json(),
        )

        service = Service()
        service.load_from_data_source(source)

        assert service.is_healthy()
        assert service.is_ready()

        employee = service.get_employee_by_uid("testuser1")
        assert employee is not None
        assert employee.full_name == "Test User One"

    def test_service_hot_reload_from_fake_gcs(self) -> None:
        """Test hot reloading service data from fake GCS."""
        # Create initial data with 2 employees
        source = FakeGCSDataSource(
            bucket="org-data",
            object_path="data.json",
            content=create_test_data_json(),
        )

        service = Service()
        service.load_from_data_source(source)

        version1 = service.get_version()
        assert version1.employee_count == 2

        # Reload with same data
        service.load_from_data_source(source)

        version2 = service.get_version()
        assert version2.employee_count == 2
        assert version2.load_time >= version1.load_time


class TestRetryWithBackoff:
    """Tests for the retry with backoff utility."""

    def test_successful_operation(self) -> None:
        """Test that successful operation returns immediately."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            return b"success"

        result = _retry_with_backoff(operation, max_retries=3, initial_delay=0.01)
        assert result == b"success"
        assert call_count == 1

    def test_retry_on_failure(self) -> None:
        """Test that operation is retried on failure."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return b"success"

        result = _retry_with_backoff(operation, max_retries=3, initial_delay=0.01)
        assert result == b"success"
        assert call_count == 3

    def test_exhausted_retries_raises(self) -> None:
        """Test that GCSError is raised when retries are exhausted."""

        def operation():
            raise Exception("Persistent error")

        with pytest.raises(GCSError, match="failed after"):
            _retry_with_backoff(operation, max_retries=2, initial_delay=0.01)


class TestGCSConfig:
    """Tests for GCS configuration."""

    def test_config_defaults(self) -> None:
        """Test default configuration values."""
        config = GCSConfig(bucket="test", object_path="data.json")
        assert config.bucket == "test"
        assert config.object_path == "data.json"
        assert config.project_id == ""
        assert config.credentials_json == ""

    def test_config_with_all_options(self) -> None:
        """Test configuration with all options."""
        from datetime import timedelta

        config = GCSConfig(
            bucket="my-bucket",
            object_path="path/to/data.json",
            project_id="my-project",
            credentials_json='{"type": "service_account"}',
            check_interval=timedelta(minutes=10),
        )
        assert config.bucket == "my-bucket"
        assert config.project_id == "my-project"
        assert config.check_interval.total_seconds() == 600
