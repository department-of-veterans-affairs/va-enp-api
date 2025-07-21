"""Tests for recipient identifiers DAO methods."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Row, delete, select
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.constants import IdentifierType
from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.recipient_identifiers_dao import RecipientIdentifiersDao
from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel


class TestLegacyRecipientIdentifiersDaoSet:
    """Test class for LegacyRecipientIdentifiersDao set_recipient_identifiers."""

    @pytest.mark.parametrize(
        ('id_type', 'id_value'),
        [
            (IdentifierType.BIRLSID, '12345'),
            (IdentifierType.EDIPI, '12345'),
            (IdentifierType.ICN, '1234567890V123456'),
            (IdentifierType.PID, '12345'),
            (IdentifierType.VA_PROFILE_ID, '12345'),
        ],
    )
    async def test_happy_path(self, id_type: IdentifierType, id_value: str, commit_notification: Row[Any]) -> None:
        """Test the ability to add a recipient identifier to the database.

        Args:
            id_type: Recipient identifier IdentifierType
            id_value: Recipient identifier value
            commit_notification (Row[Any]): Notification that was committed to the database
        """
        recipient = RecipientIdentifierModel(id_type=id_type, id_value=id_value)
        await RecipientIdentifiersDao.set_recipient_identifiers(
            notification_id=commit_notification.id, recipient_identifiers=recipient
        )

        # Verify that the data was persisted to the database
        legacy_recipient_identifiers = metadata_legacy.tables['recipient_identifiers']

        async with get_write_session_with_context() as session:
            result = await session.execute(
                select(legacy_recipient_identifiers).where(
                    legacy_recipient_identifiers.c.notification_id == commit_notification.id
                )
            )
            persisted_recipient = result.fetchone()

            # Verify the expected data is present
            assert persisted_recipient is not None, 'Expected recipient identifier to be found in database'
            assert persisted_recipient.id_type == id_type.value
            assert persisted_recipient.id_value == id_value
            assert persisted_recipient.notification_id == commit_notification.id

        # tear down, notification cleanup up by commit_notification fixture
        async with get_write_session_with_context() as session:
            await session.execute(
                delete(legacy_recipient_identifiers).where(
                    legacy_recipient_identifiers.c.notification_id == commit_notification.id
                )
            )
            await session.commit()

    async def test_set_recipient_identifiers_raise_non_retryable_for_db_constraint(
        self, commit_notification: Row[Any]
    ) -> None:
        """Test that set_recipient_identifiers raises NonRetryableError when database constraint is violated.

        Args:
            commit_notification (Row[Any]): Notification that was committed to the database
        """
        recipient = RecipientIdentifierModel(id_type=IdentifierType.PID, id_value='12345')

        # First insertion should succeed
        await RecipientIdentifiersDao.set_recipient_identifiers(
            notification_id=commit_notification.id, recipient_identifiers=recipient
        )

        # Second insertion with same notification_id should fail with NonRetryableError
        # due to IntegrityError (duplicate key constraint violation)
        with pytest.raises(NonRetryableError):
            await RecipientIdentifiersDao.set_recipient_identifiers(
                notification_id=commit_notification.id, recipient_identifiers=recipient
            )

        legacy_recipient_identifiers = metadata_legacy.tables['recipient_identifiers']

        # tear down, notification cleanup up by commit_notification fixture
        async with get_write_session_with_context() as session:
            await session.execute(
                delete(legacy_recipient_identifiers).where(
                    legacy_recipient_identifiers.c.notification_id == commit_notification.id
                )
            )
            await session.commit()

    @pytest.mark.parametrize(
        'caught_exception',
        [
            IntegrityError('stmt', 'params', Exception('orig')),
            DataError('stmt', 'params', Exception('orig')),
            OperationalError('stmt', 'params', Exception('orig')),
            InterfaceError('stmt', 'params', Exception('orig')),
            TimeoutError(),
            SQLAlchemyError('some generic error'),
            Exception('some other error'),
        ],
    )
    async def test_set_recipient_identifiers_all_exceptions_non_retryable(
        self,
        caught_exception: Exception,
    ) -> None:
        """Test that set_recipient_identifiers raises NonRetryableError for all exception types.

        Args:
            caught_exception (Exception): The exception our code caught
        """
        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.recipient_identifiers_dao.get_write_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            recipient = RecipientIdentifierModel(id_type=IdentifierType.PID, id_value='12345')

            with pytest.raises(NonRetryableError):
                await RecipientIdentifiersDao.set_recipient_identifiers(
                    notification_id=uuid4(), recipient_identifiers=recipient
                )

    @pytest.mark.parametrize(
        ('caught_exception', 'raised_exception'),
        [
            (IntegrityError('stmt', 'params', Exception('orig')), NonRetryableError),
            (DataError('stmt', 'params', Exception('orig')), NonRetryableError),
            (OperationalError('stmt', 'params', Exception('orig')), RetryableError),
            (InterfaceError('stmt', 'params', Exception('orig')), RetryableError),
            (TimeoutError(), RetryableError),
            (SQLAlchemyError('some generic error'), NonRetryableError),
            (Exception('some other error'), NonRetryableError),
        ],
    )
    async def test_set_recipient_identifiers_exception_handling(
        self,
        caught_exception: Exception,
        raised_exception: type[Exception],
    ) -> None:
        """Test that _set_recipient_identifiers raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (type[Exception]): The exception type we expect to be raised by our code
        """
        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.recipient_identifiers_dao.get_write_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            recipient = RecipientIdentifierModel(id_type=IdentifierType.PID, id_value='12345')

            with pytest.raises(raised_exception):
                await RecipientIdentifiersDao._set_recipient_identifiers(
                    notification_id=uuid4(), recipient_identifiers=recipient
                )
