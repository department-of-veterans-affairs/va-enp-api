"""All endpoints for the v3/notifications route."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import UUID4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from app.db.db_init import get_api_read_session_with_depends
from app.routers import TimedAPIRoute
from app.v3.notifications.route_schema import NotificationSingleRequest, NotificationSingleResponse

api_router = APIRouter(
    prefix='/notifications',
    route_class=TimedAPIRoute,
)


# This endpoint needs a read connection to the api database
@api_router.get(
    '/{notification_id}',
    status_code=status.HTTP_200_OK,
)
async def get_notification(notification_id: UUID4, db_session: Annotated[async_scoped_session[AsyncSession], Depends(get_api_read_session_with_depends)]) -> UUID4:
    """Get a notification.

    Args:
        notification_id (UUID4): The notification to get

    Returns:
        UUID4: The notification object

    """
    async with db_session() as session:
        sql = "SELECT * FROM notifications WHERE id = :notification_id"
        result = await session.execute(text(sql), {'notification_id': str(notification_id)})
        notification = result.fetchone()
        logger.debug(f'Notification: {notification}')
        if not notification:
            logger.error(f'Notification with id {notification_id} not found')
            # Raise a HTTP 404
            raise HTTPException(status_code=404, detail='Notification not found') 
    return notification.id


@api_router.post('/', status_code=status.HTTP_202_ACCEPTED)
async def create_notification(request: NotificationSingleRequest) -> NotificationSingleResponse:
    """Return app status.

    Args:
        request (NotificationSingleRequest): Data for the request

    Returns:
        UUID4: The notification object

    """
    response = NotificationSingleResponse(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        to=request.to,
    )
    return response
