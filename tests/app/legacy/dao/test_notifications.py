"""Tests for notifications DAO methods."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.engine import Row
from sqlalchemy.exc import (
    DataError,
    InterfaceError,
    MultipleResultsFound,
    NoResultFound,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.notifications_dao import LegacyNotificationDao


class TestLegacyNotificationDaoGet:
    """Test class for LegacyNotificationDao.get method."""

    async def test_get_happy_path(self, commit_notification: Row[Any]) -> None:
        """Test the ability to get a notification from the database.

        Args:
            commit_notification (Row[Any]): Notification that was committed to the database
        """
        notification_row = await LegacyNotificationDao.get(commit_notification.id)
        assert notification_row.id == commit_notification.id

    async def test_get_non_existent_notification(self) -> None:
        """Should raise NoResultFound when notification does not exist in DB."""
        with pytest.raises(NonRetryableError):
            await LegacyNotificationDao.get(uuid4())

    @pytest.mark.parametrize(
        ('caught_exception', 'raised_exception'),
        [
            (NoResultFound(), NonRetryableError),
            (MultipleResultsFound(), NonRetryableError),
            (DataError('stmt', 'params', Exception('orig')), NonRetryableError),
            (OperationalError('stmt', 'params', Exception('orig')), RetryableError),
            (InterfaceError('stmt', 'params', Exception('orig')), RetryableError),
            (TimeoutError(), RetryableError),
            (SQLAlchemyError('some generic error'), NonRetryableError),
        ],
    )
    async def test_get_exception_handling(
        self,
        caught_exception: Exception,
        raised_exception: type[Exception],
    ) -> None:
        """Test that _get raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (type[Exception]): The exception our code raised
        """
        notification_id = uuid4()

        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.notifications_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyNotificationDao._get(notification_id)
