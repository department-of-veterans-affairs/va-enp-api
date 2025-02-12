"""All endpoints for the v3/notifications route."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, status
from pydantic import UUID4

from app.routers import TimedAPIRoute
from app.v3.notifications.route_schema import NotificationSingleRequest, NotificationSingleResponse

api_router = APIRouter(
    prefix='/notifications',
    route_class=TimedAPIRoute,
)


@api_router.get('/{notification_id}', status_code=status.HTTP_200_OK)
async def get_notification(notification_id: UUID4) -> UUID4:
    """Get a notification.

    Args:
        notification_id (UUID4): The notification to get

    Returns:
        UUID4: The notification object

    """
    return notification_id


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
