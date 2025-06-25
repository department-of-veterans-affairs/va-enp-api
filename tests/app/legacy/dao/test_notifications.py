"""Tests for notifications DAO methods."""

from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import Row
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    InterfaceError,
    MultipleResultsFound,
    NoResultFound,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.constants import NotificationType
from app.db.db_init import get_write_session_with_context, metadata_legacy
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


class TestLegacyNotificationDaoCreateNotification:
    """Test class for LegacyNotificationDao.create_notification method."""

    async def test_get_happy_path(
        self,
        commit_template: Row[Any],
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test the ability to create a notification in the database.

        Args:
            commit_template (Row[Any]): Template that was committed to the database
            sample_api_key (Callable): A factory fixture that returns a new API key row for a given service.
        """
        # setup
        async with get_write_session_with_context() as session:
            api_key = await sample_api_key(
                session=session,
                service_id=commit_template.service_id,
            )
            await session.commit()

        notification_id = uuid4()

        await LegacyNotificationDao.create_notification(
            id=notification_id,
            notification_type=NotificationType.SMS,
            to='888-888-8888',
            reply_to_text='111-111-1111',
            service_id=commit_template.service_id,
            api_key_id=api_key.id,
            reference=str(uuid4()),
            template_id=commit_template.id,
            template_version=commit_template.version,
            key_type=api_key.key_type,
        )

        notification_row = await LegacyNotificationDao.get(notification_id)

        assert notification_row.id == notification_id

        legacy_api_keys = metadata_legacy.tables['api_keys']
        legacy_notifications = metadata_legacy.tables['notifications']

        async with get_write_session_with_context() as session:
            await session.execute(delete(legacy_notifications).where(legacy_notifications.c.id == notification_id))
            await session.execute(delete(legacy_api_keys).where(legacy_api_keys.c.id == api_key.id))
            await session.commit()

    @pytest.mark.parametrize(
        ('caught_exception', 'raised_exception'),
        [
            (IntegrityError('stmt', 'params', Exception('orig')), NonRetryableError),
            (IntegrityError('duplicate', 'params', Exception('orig')), NonRetryableError),
            (DataError('stmt', 'params', Exception('orig')), NonRetryableError),
            (DataError('duplicate', 'params', Exception('orig')), NonRetryableError),
            (OperationalError('stmt', 'params', Exception('orig')), NonRetryableError),
            (InterfaceError('stmt', 'params', Exception('orig')), NonRetryableError),
            (TimeoutError(), NonRetryableError),
            (SQLAlchemyError('some generic error'), NonRetryableError),
        ],
    )
    async def test_create_notification_exception_handling(
        self,
        caught_exception: Exception,
        raised_exception: type[Exception],
    ) -> None:
        """Test that _insert_notification raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (type[Exception]): The exception our code raised
        """
        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.notifications_dao.get_write_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyNotificationDao.create_notification(
                    id=uuid4(),
                    notification_type=NotificationType.SMS,
                    to='888-888-8888',
                    reply_to_text='111-111-1111',
                    service_id=uuid4(),
                    api_key_id=uuid4(),
                    reference=str(uuid4()),
                    template_id=uuid4(),
                    template_version=0,
                    billable_units=0,
                    key_type='normal',
                    personalisation=None,
                )

    @pytest.mark.parametrize(
        ('caught_exception', 'raised_exception'),
        [
            (IntegrityError('stmt', 'params', Exception('orig')), NonRetryableError),
            (IntegrityError('duplicate', 'params', Exception('orig')), RetryableError),
            (DataError('stmt', 'params', Exception('orig')), NonRetryableError),
            (DataError('duplicate', 'params', Exception('orig')), RetryableError),
            (OperationalError('stmt', 'params', Exception('orig')), RetryableError),
            (InterfaceError('stmt', 'params', Exception('orig')), RetryableError),
            (TimeoutError(), RetryableError),
            (SQLAlchemyError('some generic error'), NonRetryableError),
        ],
    )
    async def test_insert_notification_exception_handling(
        self,
        caught_exception: Exception,
        raised_exception: type[Exception],
    ) -> None:
        """Test that _insert_notification raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (type[Exception]): The exception our code raised
        """
        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.notifications_dao.get_write_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyNotificationDao._insert_notification(
                    id=uuid4(),
                    notification_type=NotificationType.SMS,
                    to='888-888-8888',
                    reply_to_text='111-111-1111',
                    service_id=uuid4(),
                    api_key_id=uuid4(),
                    reference=str(uuid4()),
                    template_id=uuid4(),
                    template_version=0,
                    billable_units=0,
                    key_type='normal',
                    personalisation=None,
                )
