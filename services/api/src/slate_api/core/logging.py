"""
Logging Configuration

Centralized logging setup for the application.
- Local environment: Logs to console with colored output
- Cloud environment: Integrates with Google Cloud Logging

Usage:
    from .core.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("Application started")
    logger.error("An error occurred", exc_info=True)
"""
import logging
import sys
import warnings

from .config import settings

# Try to import Google Cloud Logging (may not be available locally)
try:
    from google.cloud import logging as cloud_logging  # type: ignore[import-untyped]

    CLOUD_LOGGING_AVAILABLE = True
except ImportError:
    CLOUD_LOGGING_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for better readability in local development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[1;31m",  # Red + Bold
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


def setup_logging() -> None:
    """
    Configure logging for the application.

    Local: colored console output, DEBUG level by default.
    Cloud (Cloud Run): Google Cloud Logging via StructuredLogHandler, INFO by default.
    """
    log_level_str = settings.effective_log_level.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    if settings.is_local:
        # ── Local: colored console ────────────────────────────────────────────
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(
            ColoredFormatter(
                fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(handler)
        root_logger.info(f"Local logging configured (level: {log_level_str})")

    else:
        # ── Cloud Run: Google Cloud Logging ───────────────────────────────────
        # StructuredLogHandler writes JSON to stdout; Cloud Run agent captures it.
        # Do NOT add extra handlers to avoid duplicate logs.
        if CLOUD_LOGGING_AVAILABLE:
            try:
                client = cloud_logging.Client()
                client.setup_logging(log_level=log_level)
                root_logger.info(f"Cloud logging configured (level: {log_level_str})")
            except Exception as e:
                _add_plain_console_handler(root_logger, log_level)
                root_logger.warning(f"Failed to setup Cloud Logging: {e}. Using console fallback.")
        else:
            _add_plain_console_handler(root_logger, log_level)
            root_logger.warning("google-cloud-logging not installed. Using console fallback.")

    _suppress_noisy_loggers()


def _add_plain_console_handler(logger: logging.Logger, level: int) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)


def _suppress_noisy_loggers() -> None:
    """Reduce log noise from verbose third-party libraries."""
    noisy = [
        "urllib3",
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
        "httpx",
        "asyncio",
        "werkzeug",
        "google.auth",
        "google.api_core",
        "sqlalchemy.engine.Engine",
    ]
    for name in noisy:
        logging.getLogger(name).setLevel(logging.WARNING)

    warnings.filterwarnings("ignore", category=RuntimeWarning, module="asyncio")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given module.

    Args:
        name: Typically ``__name__`` from the calling module.

    Returns:
        Configured ``logging.Logger`` instance.
    """
    return logging.getLogger(name)
