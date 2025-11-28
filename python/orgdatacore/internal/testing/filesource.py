"""
FileDataSource - Internal testing utility.

INTERNAL USE ONLY: This is kept for test infrastructure.
Production code should use GCSDataSource or implement a custom DataSource.

This module is NOT part of the public API and may change without notice.
"""

import os
import threading
import time
from io import BytesIO
from typing import BinaryIO, Callable, Optional

# Note: We don't inherit from DataSource - it's a Protocol (structural typing)
# Just implement the required methods: load(), watch(), __str__()


class FileDataSource:
    """
    FileDataSource loads organizational data from local files.

    INTERNAL USE ONLY: This should only be used in test code.
    Production code should use GCSDataSource or implement a custom DataSource.

    For production deployments, file-based data sources are not recommended
    for security reasons. Use GCS or implement your own DataSource (e.g., S3).
    """

    def __init__(
        self, file_paths: list[str] | str, poll_interval: float = 60.0
    ) -> None:
        """
        Create a new file-based data source for testing.

        INTERNAL USE ONLY.

        Args:
            file_paths: Path(s) to the data file(s). If multiple provided,
                       the last one is used.
            poll_interval: Interval in seconds for polling file changes.
        """
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        self.file_paths = file_paths
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()

    def load(self) -> BinaryIO:
        """Load and return a reader for the organizational data file."""
        if not self.file_paths:
            raise ValueError("no file paths provided")

        # Load the primary data file (use the last path if multiple provided)
        file_path = self.file_paths[-1]
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            return BytesIO(content)
        except FileNotFoundError:
            raise FileNotFoundError(f"failed to open file {file_path}")
        except IOError as e:
            raise IOError(f"failed to read file {file_path}: {e}")

    def watch(self, callback: Callable[[], Optional[Exception]]) -> Optional[Exception]:
        """
        Monitor for file changes and call callback when data is updated.

        This starts a background thread that polls for file changes.
        """
        if not self.file_paths:
            return ValueError("no file paths to watch")

        # Get initial modification times
        mod_times: dict[str, float] = {}
        for path in self.file_paths:
            try:
                mod_times[path] = os.path.getmtime(path)
            except OSError:
                pass

        def watcher() -> None:
            while not self._stop_event.is_set():
                time.sleep(self.poll_interval)
                if self._stop_event.is_set():
                    break

                # Check if any files have changed
                changed = False
                for path in self.file_paths:
                    try:
                        current_mtime = os.path.getmtime(path)
                        last_mtime = mod_times.get(path)
                        if last_mtime is None or current_mtime > last_mtime:
                            mod_times[path] = current_mtime
                            changed = True
                    except OSError:
                        pass

                if changed:
                    try:
                        callback()
                    except Exception:
                        # Log but don't crash the watcher
                        pass

        thread = threading.Thread(target=watcher, daemon=True)
        thread.start()
        return None

    def stop_watching(self) -> None:
        """Stop the file watcher."""
        self._stop_event.set()

    def __str__(self) -> str:
        """Return a description of this data source."""
        if len(self.file_paths) == 1:
            return f"file:{self.file_paths[0]}"
        return f"files:{','.join(self.file_paths)}"


