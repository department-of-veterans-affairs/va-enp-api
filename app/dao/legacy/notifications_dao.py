"""The data access objects for notifications."""

from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, select

from app.db.db_init import get_read_session_with_context, metadata_legacy


class LegacyNotificationDao:
    """."""

    @staticmethod
    async def get_notification(id: UUID4) -> Row[Any]:
        """Get a Notification from the legacy database.

        Args:
            id (UUID4): id of the notification

        Returns:
            Row: notification table row
        """
        async with get_read_session_with_context(False) as session:
            leg_notifications = metadata_legacy.tables['notifications']
            stmt = select(leg_notifications).where(leg_notifications.c.id == id)
            return (await session.execute(stmt)).one()
