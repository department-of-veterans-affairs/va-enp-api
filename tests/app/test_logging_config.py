"""Test suite for logging configurations with Loguru."""

import logging
import sys
from unittest.mock import ANY, patch

from app.constants import DEPLOYMENT_ENVS, ENV
from app.logging.logging_config import (
    LOGLEVEL_DEBUG,
    CustomizeLogger,
    InterceptHandler,
)


def test_make_logger() -> None:
    """Test to ensure the logger is configured correctly using CustomizeLogger."""
    with (
        patch('app.logging.logging_config.loguru_logger') as logger_mock,
    ):
        # Create references to the loggers before calling make_logger
        fastapi_logger = logging.getLogger('fastapi')
        uvicorn_loggers = [logging.getLogger(name) for name in ('uvicorn', 'uvicorn.access', 'uvicorn.error')]

        # Call the method under test
        CustomizeLogger.make_logger()

        # Check logger.add was called with correct parameters
        logger_mock.add.assert_any_call(
            sys.stdout,
            enqueue=True,
            backtrace=False,
            level=LOGLEVEL_DEBUG,
            filter=ANY,
            serialize=ENV in DEPLOYMENT_ENVS,
        )
        logger_mock.add.assert_any_call(
            sys.stderr,
            enqueue=True,
            backtrace=False,
            level='ERROR',
            serialize=ENV in DEPLOYMENT_ENVS,
        )

        # Verify that the InterceptHandler was added to the appropriate loggers
        assert all(isinstance(handler, InterceptHandler) for handler in fastapi_logger.handlers)

        for logger in uvicorn_loggers:
            assert all(isinstance(handler, InterceptHandler) for handler in logger.handlers)
