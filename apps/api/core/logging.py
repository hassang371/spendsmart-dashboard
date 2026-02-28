"""Structured logging with structlog.

Configures JSON logging for production and colorized console for dev.
Replaces all print() statements throughout the codebase (fixes ARCH-02).

Usage:
    import structlog
    logger = structlog.get_logger()
    logger.info("event_name", key="value", count=42)
"""

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Python log level string (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, use JSON renderer (production). If False,
                     use colorized console renderer (development).
    """
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
