"""Tests for recipient identifiers DAO methods."""

from typing import Any

import pytest
from sqlalchemy import Row, delete

from app.constants import IdentifierType
from app.db.db_init import get_write_session_with_context, metadata_legacy
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
