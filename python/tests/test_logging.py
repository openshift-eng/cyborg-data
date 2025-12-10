"""Tests for logging configuration."""

import logging

from orgdatacore import configure_default_logging, get_logger, set_logger


class TestLogging:
    """Test logging configuration."""

    def teardown_method(self) -> None:
        """Reset logger after each test."""
        set_logger(None)

    def test_get_default_logger(self) -> None:
        """get_logger returns the orgdatacore logger by default."""
        logger = get_logger()
        assert logger.name == "orgdatacore"

    def test_set_custom_logger(self) -> None:
        """set_logger should allow using a custom logger."""
        custom = logging.getLogger("myapp.orgdata")
        set_logger(custom)

        assert get_logger() is custom
        assert get_logger().name == "myapp.orgdata"

    def test_reset_logger(self) -> None:
        """set_logger(None) should reset to default."""
        custom = logging.getLogger("custom")
        set_logger(custom)
        assert get_logger() is custom

        set_logger(None)
        assert get_logger().name == "orgdatacore"

    def test_configure_default_logging(self) -> None:
        """configure_default_logging should set up the default logger."""
        configure_default_logging(level=logging.DEBUG)
        logger = get_logger()

        assert logger.level == logging.DEBUG
        assert len(logger.handlers) >= 1

    def test_configure_logging_idempotent(self) -> None:
        """Calling configure_default_logging twice shouldn't add extra handlers."""
        configure_default_logging(level=logging.INFO)
        initial_handlers = len(get_logger().handlers)

        configure_default_logging(level=logging.INFO)
        assert len(get_logger().handlers) == initial_handlers

