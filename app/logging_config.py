"""Setup global logging configurations using Loguru."""

import sys

from loguru import logger as loguru_logger
from loguru._logger import Logger


def configure_loguru() -> Logger:
    """Configure Loguru logging.

    Returns
    -------
    Logger: Configured Loguru logger instance.

    """
    # Remove any pre-existing loggers
    loguru_logger.remove()

    # Add a new logger that logs to stdout
    loguru_logger.add(sys.stdout, level='DEBUG', format='{time} {level} {message}')

    return loguru_logger
