"""Logging configuration for WxDXX.

Logs are written to ~/.config/wxdxx/wxdxx.log to avoid interfering with the TUI.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Log file location (same directory as config)
LOG_DIR = Path.home() / ".config" / "wxdxx"
LOG_FILE = LOG_DIR / "wxdxx.log"

# Log format with timestamp, level, module, and message
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Default log level (can be overridden via environment variable)
DEFAULT_LOG_LEVEL = logging.INFO

# Max log file size (5 MB) and backup count
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def setup_logging(level: int | None = None) -> None:
    """Configure logging for the application.

    Sets up a rotating file handler that writes to ~/.config/wxdxx/wxdxx.log.
    The TUI is not affected since we don't log to stdout/stderr.

    Args:
        level: Log level (e.g., logging.DEBUG). Defaults to INFO.
    """
    if level is None:
        level = DEFAULT_LOG_LEVEL

    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create rotating file handler
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    # Configure root logger for wxdxx package
    root_logger = logging.getLogger("wxdxx")
    root_logger.setLevel(level)

    # Remove any existing handlers (in case setup is called multiple times)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Prevent propagation to root logger (which might have console handlers)
    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance configured for this module.
    """
    return logging.getLogger(name)
