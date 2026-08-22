"""Logging configuration backed by Loguru."""

from __future__ import annotations

import sys

from loguru import logger

from config import Config


def setup_logging(config: Config) -> None:
    """Configure Loguru to write JSON logs in production and readable logs locally.

    The sink setup is idempotent enough for a single-process Flask application.
    Production uses a single file sink with rotation to keep the log output
    manageable on Render and similar platforms.
    """
    logger.remove()

    if config.flask_env == "production":
        logger.add(
            "logs/app.log",
            rotation="10 MB",
            retention="7 days",
            level="INFO",
            serialize=True,
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(sys.stderr, level="DEBUG", colorize=True)

    logger.bind(config=config).info("Logging initialized")
