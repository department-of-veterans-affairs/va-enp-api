"""Tests for recipient identifiers DAO methods."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Row, delete
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

        # tear down, notification cleanup up by commit_notification fixture
        legacy_recipient_identifiers = metadata_legacy.tables['recipient_identifiers']

        async with get_write_session_with_context() as session:
            await session.execute(
                delete(legacy_recipient_identifiers).where(
                    legacy_recipient_identifiers.c.notification_id == commit_notification.id
                )
            )
            await session.commit()

    async def test_sad_path(self, commit_notification: Row[Any]) -> None:
        """Test the ability to add a recipient identifier to the database.

        Args:
            commit_notification (Row[Any]): Notification that was committed to the database
        """
        with pytest.raises(NonRetryableError):
            await RecipientIdentifiersDao.set_recipient_identifiers(
                notification_id=commit_notification.id, recipient_identifiers='not a recipient identifier'
            )

        # tear down, notification cleanup up by commit_notification fixture
        legacy_recipient_identifiers = metadata_legacy.tables['recipient_identifiers']

        async with get_write_session_with_context() as session:
            await session.execute(
                delete(legacy_recipient_identifiers).where(
                    legacy_recipient_identifiers.c.notification_id == commit_notification.id
                )
            )
            await session.commit()

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
        raised_exception: Exception,
    ) -> None:
        """Test that _set_recipient_identifiers raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (Exception): The exception we expect to be raised by our code
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
