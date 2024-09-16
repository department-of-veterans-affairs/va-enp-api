"""Test suite for logging configurations with Loguru."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from app.logging_config import CustomizeLogger, InterceptHandler


@pytest.fixture
def logger_mock() -> MagicMock:
    """Fixture to mock the logger object from app.logging_config.

    Yields:
    MagicMock: The mock logger object.

    """
    with patch('app.logging_config.logger') as mock_logger:
        yield mock_logger


@pytest.fixture
def mock_logging_config() -> dict:
    """Fixture to provide a mock logging configuration.

    Returns:
    dict: Mock logging configuration dictionary.

    """
    return {
        'path': 'app.log',
        'level': 'DEBUG',
        'rotation': '1 week',
        'retention': '30 days',
        'format': '{time} {level} {message}',
    }


def test_make_logger(logger_mock: MagicMock, mock_logging_config: dict) -> None:
    """Test to ensure the logger is configured correctly using CustomizeLogger."""
    with (
        patch('app.logging_config.CustomizeLogger.load_config', return_value=mock_logging_config),
        patch('logging.getLogger') as mock_get_logger,
        patch.dict('os.environ', {'SERVER_SOFTWARE': 'gunicorn'}),
    ):
        # Mocking individual loggers
        fastapi_logger = MagicMock()
        uvicorn_logger = MagicMock()
        gunicorn_logger = MagicMock()

        # Dynamically returns a specific mock logger based on the logger name
        mock_get_logger.side_effect = lambda name: {
            'fastapi': fastapi_logger,
            'uvicorn.access': uvicorn_logger,
            'uvicorn': uvicorn_logger,
            'uvicorn.error': uvicorn_logger,
            'gunicorn.error': gunicorn_logger,
            'gunicorn.access': gunicorn_logger,
        }.get(name, MagicMock())

        CustomizeLogger.make_logger()

        # Check logger.add was called with correct parameters
        logger_mock.add.assert_any_call(
            sys.stdout, enqueue=True, backtrace=True, level='DEBUG', format='{time} {level} {message}'
        )
        logger_mock.add.assert_any_call(
            'app.log',
            rotation='1 week',
            retention='30 days',
            enqueue=True,
            backtrace=True,
            level='DEBUG',
            format='{time} {level} {message}',
        )

        # Verify FastAPI logger is assigned InterceptHandler
        mock_get_logger.assert_any_call('fastapi')
        assert isinstance(fastapi_logger.handlers[0], InterceptHandler)

        # Verify Uvicorn loggers are assigned InterceptHandler
        mock_get_logger.assert_any_call('uvicorn.access')
        mock_get_logger.assert_any_call('uvicorn')
        mock_get_logger.assert_any_call('uvicorn.error')
        assert isinstance(uvicorn_logger.handlers[0], InterceptHandler)

        # Verify Gunicorn loggers are assigned InterceptHandler
        mock_get_logger.assert_any_call('gunicorn.error')
        mock_get_logger.assert_any_call('gunicorn.access')
        assert isinstance(gunicorn_logger.handlers[0], InterceptHandler)
