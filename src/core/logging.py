"""
Logging Configuration

Centralized logging setup with structured output.
"""

import logging
import sys

from src.core.config import settings


def setup_logging() -> None:
    """
    Configure application logging.

    Sets up:
    - Log level from settings
    - Console handler with ISO timestamp format
    - Filters for third-party libraries (SQLAlchemy, httpx)
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
