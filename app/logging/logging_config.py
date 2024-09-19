"""Create custom logging with Loguru."""

from __future__ import annotations

import json
import logging
import os
import sys
from types import FrameType
from typing import Dict, Optional

import loguru
from loguru import logger as loguru_logger

LOGGING_CONFIG_PATH = 'app/logging/logging_config.json'

LOGLEVEL_CRITICAL = 'CRITICAL'
LOGLEVEL_ERROR = 'ERROR'
LOGLEVEL_WARNING = 'WARNING'
LOGLEVEL_INFO = 'INFO'
LOGLEVEL_DEBUG = 'DEBUG'
LOGLEVEL_NOTSET = 'NOTSET'

LOGLEVEL_MAPPING: Dict[int, str] = {
    50: LOGLEVEL_CRITICAL,
    40: LOGLEVEL_ERROR,
    30: LOGLEVEL_WARNING,
    20: LOGLEVEL_INFO,
    10: LOGLEVEL_DEBUG,
    0: LOGLEVEL_NOTSET,
}


class InterceptHandler(logging.Handler):
    """Intercept standard logging and route it through Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a standard log record using Loguru.

        Args:
        ----
        record : logging.LogRecord
            The log record to be emitted through Loguru.

        """
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = LOGLEVEL_MAPPING.get(record.levelno, 'INFO')

        # Find the correct frame to display the source of the log message
        frame: Optional[FrameType] = logging.currentframe()
        if frame is not None:
            depth = 2
            while frame is not None and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            # Log the message with Loguru
            log = loguru_logger.bind(request_id='app')
            log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class CustomizeLogger:
    """Customizes and configures Loguru logging for FastAPI, Uvicorn, and Gunicorn."""

    @classmethod
    def make_logger(cls) -> loguru.Logger:
        """Create and configure the Loguru logger using an external configuration file.

        Returns
        -------
            logger: Configured Loguru logger instance.

        """
        logging_config = cls.load_config()

        # Create the custom Loguru logger
        log = cls.customize_logging(
            filepath=logging_config['path'],
            level=logging_config['level'],
            rotation=logging_config['rotation'],
            retention=logging_config['retention'],
        )

        # Configure specific Loguru loggers for FastAPI, Uvicorn, and Gunicorn
        cls._configure_fastapi_logger()
        cls._configure_uvicorn_logger()
        cls._configure_gunicorn_logger()

        return log

    @classmethod
    def load_config(cls) -> Dict[str, str]:
        """Load logging configuration from a JSON file.

        Raises
        ------
        FileNotFoundError
            If the configuration file is not found at the expected path.
        JSONDecodeError
            If the configuration file cannot be parsed as valid JSON.

        Returns
        -------
            dict: Logging configuration loaded from the JSON file.

        """
        try:
            with open(LOGGING_CONFIG_PATH, 'r') as file:
                return dict(json.load(file))
        except FileNotFoundError:
            loguru_logger.critical('Logging configuration file not found at {}', LOGGING_CONFIG_PATH)
            raise
        except json.JSONDecodeError:
            loguru_logger.critical('Error decoding logging configuration file at {}', LOGGING_CONFIG_PATH)
            raise

    @classmethod
    def customize_logging(
        cls,
        filepath: str,
        level: str,
        rotation: str,
        retention: str,
    ) -> loguru.Logger:
        """Customize Loguru logging with specific configurations.

        Args:
        ----
        filepath : str
            Path to the log file where logs will be written.
        level : str
            The logging level to be used (e.g., 'DEBUG', 'INFO').
        rotation : str
            Log rotation policy (e.g., '1 day', '100 MB').
        retention : str
            Log retention policy (e.g., '10 days', '1 year').

        Returns:
        -------
        logger
            The Loguru logger instance, bound with additional context such as request_id and method.

        """
        # Remove existing handlers
        logging.getLogger().handlers = []

        # Remove Loguru's default handler
        loguru_logger.remove()

        # Add a logger to stdout
        loguru_logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
        )

        # Add a logger to a file with rotation and retention
        loguru_logger.add(
            str(filepath),
            rotation=rotation,
            retention=retention,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
        )

        # Return the logger bound with additional context
        return loguru_logger.bind(request_id=None, method=None)

    @classmethod
    def _configure_fastapi_logger(cls) -> None:
        """Configure FastAPI to use Loguru for logging."""
        logging.getLogger('fastapi').handlers = [InterceptHandler()]
        loguru_logger.info('FastAPI logger has been configured with Loguru.')

    @classmethod
    def _configure_uvicorn_logger(cls) -> None:
        """Configure Uvicorn to use Loguru for logging."""
        for logger_name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
            uvicorn_logger = logging.getLogger(logger_name)
            uvicorn_logger.handlers = [InterceptHandler()]
            uvicorn_logger.propagate = True
        loguru_logger.info('Uvicorn logger -has been configured with Loguru.')

    @classmethod
    def _configure_gunicorn_logger(cls) -> None:
        """Configure Gunicorn to use Loguru for error and access logs."""
        if 'gunicorn' in os.environ.get('SERVER_SOFTWARE', ''):
            logging.getLogger('gunicorn.error').handlers = [InterceptHandler()]
            logging.getLogger('gunicorn.access').handlers = [InterceptHandler()]
            loguru_logger.info('Gunicorn logger has been configured with Loguru.')
