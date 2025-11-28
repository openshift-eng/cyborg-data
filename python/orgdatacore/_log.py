"""Logging configuration for orgdatacore.

This module provides structured logging support matching the Go library's
logging capabilities.

Usage:
    from orgdatacore import get_logger, set_logger

    # Use the default logger
    logger = get_logger()
    logger.info("Data loaded", extra={"employee_count": 100})

    # Set a custom logger
    import logging
    custom_logger = logging.getLogger("my_app.orgdata")
    set_logger(custom_logger)

    # Or configure the default logger
    import logging
    logging.getLogger("orgdatacore").setLevel(logging.DEBUG)
"""

import logging
from typing import Optional

# Default logger for the library
_logger: Optional[logging.Logger] = None

# Default logger name
LOGGER_NAME = "orgdatacore"


def get_logger() -> logging.Logger:
    """Get the current logger for orgdatacore.

    Returns the custom logger if set, otherwise returns the default
    library logger.

    Returns:
        The configured logger instance.
    """
    global _logger
    if _logger is not None:
        return _logger
    return logging.getLogger(LOGGER_NAME)


def set_logger(logger: Optional[logging.Logger]) -> None:
    """Set a custom logger for orgdatacore.

    This allows integrating orgdatacore logging with your application's
    logging infrastructure.

    Args:
        logger: Custom logger to use, or None to reset to default.

    Example:
        import logging
        from orgdatacore import set_logger

        # Use your application's logger
        app_logger = logging.getLogger("myapp.orgdata")
        set_logger(app_logger)
    """
    global _logger
    _logger = logger


def configure_default_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
) -> None:
    """Configure the default orgdatacore logger.

    Convenience function to set up basic logging configuration.

    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (default: structured format)

    Example:
        from orgdatacore import configure_default_logging
        import logging

        configure_default_logging(level=logging.DEBUG)
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)

        if format_string is None:
            format_string = "[%(name)s] %(levelname)s: %(message)s"

        formatter = logging.Formatter(format_string)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

