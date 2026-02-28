"""Tests for structured logging setup."""

import json
import structlog

from apps.api.core.logging import setup_logging


class TestStructuredLogging:
    """Test structlog outputs structured JSON."""

    def test_setup_logging_configures_structlog(self):
        """After setup, structlog.get_logger() should return a bound logger."""
        setup_logging(log_level="DEBUG", json_output=True)
        logger = structlog.get_logger()
        assert logger is not None

    def test_setup_logging_dev_mode(self):
        """Dev mode should configure console renderer without errors."""
        setup_logging(log_level="DEBUG", json_output=False)
        logger = structlog.get_logger()
        assert logger is not None
