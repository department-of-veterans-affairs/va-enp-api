"""Create custom logging with Loguru."""

from __future__ import annotations

import logging
import sys
from contextlib import suppress
from types import FrameType
from typing import Dict, Optional

from loguru import logger as loguru_logger
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.constants import DEPLOYMENT_ENVS, ENV

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

# Serialize (json logging) if the env variable ENV is dev, perf, staging, or prod
SERIALIZE = ENV in DEPLOYMENT_ENVS


def get_context() -> dict[str, str]:
    """Return the context for the logger.

    Returns:
        dict[str, str]: The context for the logger

    """
    import os

    ctx = {}
    with suppress(ContextDoesNotExistError):
        ctx = context.data

    # Ensure worker_id is always present, even outside of request context
    if 'worker_id' not in ctx:
        ctx['worker_id'] = str(os.getpid())

    return ctx


# Define the logger after the get_context function is defined
logger = loguru_logger.patch(lambda r: r['extra'].update(**get_context()))


class InterceptHandler(logging.Handler):
    """Intercept standard logging and route it through Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a standard log record using Loguru.

        Args:
            record (logging.LogRecord): The log record to be emitted through Loguru.

        """
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = LOGLEVEL_MAPPING.get(record.levelno, 'INFO')
            loguru_logger.warning('No log level matching Loguru log level for incoming log: {}', record.getMessage())

        # Find the correct frame to display the source of the log message
        frame: Optional[FrameType] = logging.currentframe()
        if frame is not None:
            depth = 2
            while frame is not None and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            # Log the message with Loguru
            loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class CustomizeLogger:
    """Customizes and configures Loguru logging for FastAPI and Uvicorn."""

    @classmethod
    def make_logger(cls) -> None:
        """Create and configure the Loguru logger."""
        # Create the custom Loguru logger
        cls.customize_logging()

        # Configure specific Loguru loggers for FastAPI, Uvicorn, and Gunicorn
        cls._configure_fastapi_logger()
        cls._configure_uvicorn_logger()

    @classmethod
    def customize_logging(
        cls,
    ) -> None:
        """Create sinks for sys.stdout and sys.stderr with Loguru."""
        # Remove any existing handlers
        logging.getLogger().handlers = []

        # Remove Loguru's default handler
        loguru_logger.remove()

        # Add sink to stdout
        # Limit stdout sink to DEBUG, INFO, and WARNING log levels to avoid duplicate logs after adding stderr sink
        stdout_allowed_levels = (LOGLEVEL_DEBUG, LOGLEVEL_INFO, LOGLEVEL_WARNING)
        loguru_logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=False,
            level=LOGLEVEL_DEBUG,
            filter=lambda record: record['level'].name in stdout_allowed_levels,
            serialize=SERIALIZE,
        )

        # Add sink to stderr
        # Limit stderr to ERROR and higher log levels only
        loguru_logger.add(
            sys.stderr,
            enqueue=True,
            backtrace=False,
            level=LOGLEVEL_ERROR,
            serialize=SERIALIZE,
        )

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
