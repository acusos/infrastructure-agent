"""Tests for the logging utility."""

import logging

from infra_agent_v2.utils.logging import setup_logging


class TestSetupLogging:

    def test_returns_logger(self):
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_default_name(self):
        logger = setup_logging()
        assert logger.name == "infra_agent"

    def test_custom_name(self):
        logger = setup_logging(name="test_logger")
        assert logger.name == "test_logger"

    def test_default_level_info(self):
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_explicit_level_debug(self):
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_handler_exists(self):
        logger = setup_logging(name="test_unique_name")
        assert len(logger.handlers) > 0

    def test_handler_level_matches(self):
        logger = setup_logging(level="DEBUG")
        handler = logger.handlers[0]
        assert handler.level == logging.DEBUG

    def test_does_not_add_duplicate_handler(self):
        logger = setup_logging(name="dedup_test")
        initial_count = len(logger.handlers)
        setup_logging(name="dedup_test")
        assert len(logger.handlers) == initial_count
