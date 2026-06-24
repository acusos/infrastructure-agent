"""Logging setup for Infra Agent v2."""

import logging
import os
import sys
from typing import Optional


def setup_logging(level: Optional[str] = None, name: str = "infra_agent") -> logging.Logger:
    """Configure and return a logger for the agent.

    Args:
        level: Log level string (e.g. ``"DEBUG"``, ``"INFO"``). Defaults to
               ``INFRA_LOG_LEVEL`` env var or ``"INFO"``.
        name: Logger name.

    Returns:
        Configured ``logging.Logger`` instance.
    """
    if level is None:
        level = os.getenv("INFRA_LOG_LEVEL", "INFO")

    logger = logging.getLogger(name)
    logger.setLevel(level.upper())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level.upper())

        fmt = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    else:
        for handler in logger.handlers:
            handler.setLevel(level.upper())

    return logger
