"""The data access objects for notifications."""

from app.db.db_init import get_write_session_with_context
from app.db.models import Notification


# there are not tests for this yet because we have not included the database in our tests
# Note: We might be heading in a different direction regarding database access. This should be considered a placeholder.
async def dao_create_notification(notification: Notification) -> Notification:
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
