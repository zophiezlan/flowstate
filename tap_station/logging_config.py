"""
Logging Configuration

This module provides centralized logging configuration for the tap station
application. It consolidates logging setup from main.py and other modules.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


# Default logging format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Console format (shorter for readability)
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S"

# Log levels mapping
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logging(
    log_path: str = "logs/tap-station.log",
    log_level: str = "INFO",
    max_size_mb: int = 10,
    backup_count: int = 3,
    console_output: bool = True,
    file_output: bool = True,
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        log_path: Path to the log file
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_size_mb: Maximum log file size in MB before rotation
        backup_count: Number of backup log files to keep
        console_output: Enable console (stdout) logging
        file_output: Enable file logging

    Returns:
        The root logger configured for the application
    """
    # Get numeric log level
    level = LOG_LEVELS.get(log_level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # File handler with rotation
    if file_output:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        )
        root_logger.addHandler(file_handler)

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(
            logging.Formatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATE_FORMAT)
        )
        root_logger.addHandler(console_handler)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={log_level}, path={log_path}")

    return root_logger


def setup_logging_from_config(config) -> logging.Logger:
    """
    Configure logging from a Config object.

    Args:
        config: Config object with logging settings

    Returns:
        The root logger configured for the application
    """
    return setup_logging(
        log_path=config.log_path,
        log_level=config.log_level,
        max_size_mb=config.log_max_size_mb,
        backup_count=config.log_backup_count,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger by name.

    This is a convenience wrapper around logging.getLogger that ensures
    consistent logger naming across the application.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class that provides a logger attribute.

    Usage:
        class MyClass(LoggerMixin):
            def do_something(self):
                self.logger.info("Doing something")
    """

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class"""
        if not hasattr(self, "_logger"):
            self._logger = logging.getLogger(
                f"{self.__class__.__module__}.{self.__class__.__name__}"
            )
        return self._logger


def configure_module_logger(
    module_name: str,
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Configure a logger for a specific module.

    Args:
        module_name: Module name (typically __name__)
        level: Optional level override for this module

    Returns:
        Configured logger for the module
    """
    logger = logging.getLogger(module_name)
    if level:
        logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
    return logger


def silence_module(module_name: str) -> None:
    """
    Silence a noisy third-party module.

    Args:
        module_name: Module name to silence (e.g., "werkzeug")
    """
    logging.getLogger(module_name).setLevel(logging.WARNING)


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """
    Log an exception with context.

    Args:
        logger: Logger to use
        message: Context message
        exc: Exception to log
    """
    logger.error(f"{message}: {type(exc).__name__}: {exc}", exc_info=True)
