"""Test suite for logging configuration with Loguru."""

import sys
from unittest.mock import patch

from loguru import logger as loguru_logger

from app.logging_config import configure_loguru


def test_configure_loguru() -> None:
    """Test the configure_loguru function."""
    with patch.object(loguru_logger, 'add') as mock_add, patch.object(loguru_logger, 'remove') as mock_remove:
        configure_loguru()

        mock_remove.assert_called_once()

        mock_add.assert_called_once_with(sys.stdout, level='DEBUG', format='{time} {level} {message}')
