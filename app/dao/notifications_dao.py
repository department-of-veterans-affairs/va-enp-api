"""The data access objects for notifications."""

from app.db.db_init import get_write_session_with_context
from app.db.models import Notification


async def create_notification(notification: Notification) -> Notification:
    """Create a notification in the database.

    Args:
        notification (Notification): The notification to create
        db_session (async_scoped_session[AsyncSession]): The database session

    Returns:
        Notification: The created notification

    """
    async with get_write_session_with_context() as session:
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
    return notification
