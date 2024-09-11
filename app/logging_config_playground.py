"""Playground to test code from https://medium.com/1mgofficial/how-to-override-uvicorn-logger-in-fastapi-using-loguru-124133cdcd4e."""

import logging
import sys
from pathlib import Path
from typing import ClassVar

from loguru import logger


class InterceptHandler(logging.Handler):
    """Handler that intercepts standard Python logging events.

    Routes them through Loguru's logger, maintaining compatibility
    with libraries that use the standard logging module.
    """

    loglevel_mapping: ClassVar[dict[int, str]] = {
        50: 'CRITICAL',
        40: 'ERROR',
        30: 'WARNING',
        20: 'INFO',
        10: 'DEBUG',
        0: 'NOTSET',
    }

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record using Loguru's logger.

        The log level is mapped from the standard logging level to Loguru.
        """
        try:
            # Get the corresponding Loguru log level
            level = logger.level(record.levelname).name
        except AttributeError:
            # Fallback to mapped log level if level name doesn't exist
            level = self.loglevel_mapping[record.levelno]

        # Find the correct frame to display the source of the log message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Log the message with Loguru
        log = logger.bind(request_id='app')
        log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class CustomizeLogger:
    """A class to customize Loguru logger configuration using an in-file configuration."""

    @classmethod
    def make_logger(cls) -> logger:
        """Create and configure the Loguru logger using an internal configuration.

        Returns
        -------
            logger: Configured Loguru logger instance.

        """
        logging_config = {
            'path': 'app.log',  # Log file path
            'level': 'DEBUG',  # Logging level (e.g., DEBUG, INFO)
            'rotation': '1 week',  # Log rotation policy (e.g., daily, weekly)
            'retention': '30 days',  # Retention period for old logs
            'format': '{time} {level} {message}',  # Log format
        }

        return cls.customize_logging(
            filepath=logging_config['path'],
            level=logging_config['level'],
            rotation=logging_config['rotation'],
            retention=logging_config['retention'],
            format=logging_config['format'],
        )

    @classmethod
    def customize_logging(cls, filepath: Path, level: str, rotation: str, retention: str, format: str) -> logger:
        """Customize Loguru logger with specified configurations.

        Args:
        ----
            filepath (Path): Path to the log file.
            level (str): Log level (e.g., DEBUG, INFO).
            rotation (str): Log file rotation policy (e.g., daily, weekly).
            retention (str): Log file retention policy (e.g., 30 days).
            format (str): Log format for the output.

        Returns:
        -------
            logger: Configured Loguru logger instance.

        """
        # Remove the default logger
        logger.remove()

        # Add a logger to stdout
        logger.add(sys.stdout, enqueue=True, backtrace=True, level=level.upper(), format=format)

        # Add a logger to a file with rotation and retention
        logger.add(
            str(filepath),
            rotation=rotation,
            retention=retention,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
            format=format,
        )

        # Set up intercept handler for standard Python logging
        logging.basicConfig(handlers=[InterceptHandler()], level=0)

        # Override Uvicorn's default logging handlers
        logging.getLogger('uvicorn.access').handlers = [InterceptHandler()]
        for _log in ['uvicorn', 'uvicorn.error', 'fastapi']:
            _logger = logging.getLogger(_log)
            _logger.handlers = [InterceptHandler()]

        # Return the logger bound with additional context
        return logger.bind(request_id=None, method=None)
