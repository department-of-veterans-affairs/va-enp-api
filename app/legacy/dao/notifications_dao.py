"""The data access objects for notifications."""

from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, select

from app.db.db_init import get_read_session_with_context, metadata_legacy


class LegacyNotificationDao:
    """A class to handle the data access for notifications in the legacy database.

    Methods:
        get_notification: Get a Notification from the legacy database.
    """

    @staticmethod
    async def get_notification(id: UUID4) -> Row[Any]:
        """Get a Notification from the legacy database.

        Args:
            id (UUID4): id of the notification

        Returns:
            Row: notification table row
        """
        async with get_read_session_with_context() as session:
            legacy_notifications = metadata_legacy.tables['notifications']
            stmt = select(legacy_notifications).where(legacy_notifications.c.id == id)
            return (await session.execute(stmt)).one()
