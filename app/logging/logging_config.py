"""Create custom logging with Loguru."""

from __future__ import annotations

import logging
import sys
from types import FrameType
from typing import Dict, Optional

import loguru
from loguru import logger as loguru_logger

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
        """Create and configure the Loguru logger.

        Returns
        -------
            logger: Configured Loguru logger instance.

        """
        # Create the custom Loguru logger
        log = cls.customize_logging()

        # Configure specific Loguru loggers for FastAPI, Uvicorn, and Gunicorn
        cls._configure_fastapi_logger()
        cls._configure_uvicorn_logger()
        cls._configure_gunicorn_logger()

        return log

    @classmethod
    def customize_logging(
        cls,
    ) -> loguru.Logger:
        """Customize Loguru logging with specific configurations.

        Returns
        -------
        logger
            The Loguru logger instance, bound with additional context such as request_id and method.

        """
        # Remove any existing handlers
        logging.getLogger().handlers = []

        # Remove Loguru's default handler
        loguru_logger.remove()

        # Add a logger to stdout
        loguru_logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=False,
            level=LOGLEVEL_DEBUG,
        )

        # Add a logger to stderr
        # ERROR and CRITICAL only
        loguru_logger.add(
            sys.stderr,
            enqueue=True,
            backtrace=False,
            level=LOGLEVEL_ERROR,
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

            # Set to False to avoid duplicate logs
            uvicorn_logger.propagate = False
        loguru_logger.info('Uvicorn logger has been configured with Loguru.')

    @classmethod
    def _configure_gunicorn_logger(cls) -> None:
        """Configure Gunicorn to use Loguru for error and access logs."""
        logging.getLogger('gunicorn.error').handlers = [InterceptHandler()]
        logging.getLogger('gunicorn.access').handlers = [InterceptHandler()]
        loguru_logger.info('Gunicorn logger has been configured with Loguru.')
