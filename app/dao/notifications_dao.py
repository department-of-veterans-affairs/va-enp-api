"""The data access objects for notifications."""

from pydantic import UUID4
from sqlalchemy import text
from app.db.db_init import get_api_read_session_with_context, get_write_session_with_context, _metadata_legacy
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


async def dao_get_legacy_notification(notification_id: UUID4):
    async with get_api_read_session_with_context() as session:
        query = text('SELECT * FROM notifications WHERE id = :id')
        result = await session.execute(query, {'id': notification_id})
        notification = result.fetchone()
    return notification
