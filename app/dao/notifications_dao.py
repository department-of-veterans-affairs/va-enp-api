"""The data access objects for notifications."""

from loguru import logger
from pydantic import UUID4
from sqlalchemy import Row, select

from app.db.db_init import _metadata_legacy, get_api_read_session_with_context, get_write_session_with_context
from app.db.models import Notification


# there are not tests for this yet because we have not included the database in our tests
# Note: We might be heading in a different direction regarding database access. This should be considered a placeholder.
async def dao_create_notification(notification: Notification) -> Notification:  # pragma: no cover
    """Create a notification in the database. This should be considered a placeholder.

    Args:
        notification (Notification): The notification to create

    Returns:
        Notification: The notification that was added to the database

    """
    async with get_write_session_with_context() as session:
        session.add(notification)
        await session.commit()
        await session.refresh(notification)

    return notification


async def dao_get_legacy_notification(notification_id: UUID4) -> Row:
    """Get a notification from the legacy database. This should be considered a placeholder.

    Args:
        notification_id (UUID4): The ID of the notification to get

    Raises:
        ValueError: If the notification with the given ID is not found

    Returns:
        Notification: The notification from the legacy database

    """
    legacy_notifications = _metadata_legacy.tables['notifications']
    stmt = select(legacy_notifications).where(legacy_notifications.c.id == notification_id)
    async with get_api_read_session_with_context() as session:
        result = await session.execute(stmt)
        notification = result.fetchone()
    if not notification:
        raise ValueError(f'Notification with ID {notification_id} not found')

    return notification
