"""All endpoints for the v2/notifications route."""

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from loguru import logger

from app.dao.notifications_dao import dao_create_notification
from app.db.models import Notification, Template
from app.legacy.v2.notifications.route_schema import (
    V2PostPushRequestModel,
    V2PostPushResponseModel,
)
from app.legacy.v2.notifications.utils import send_push_notification_helper, validate_template
from app.routers import TimedAPIRoute

v2_notification_router = APIRouter(
    prefix='/legacy/v2/notifications',
    tags=['v2 Notification Endpoints'],
    route_class=TimedAPIRoute,
)


@v2_notification_router.post('/push', status_code=status.HTTP_201_CREATED)
async def create_push_notification(
    request_data: V2PostPushRequestModel,
    request: Request,
    background_tasks: BackgroundTasks,
) -> V2PostPushResponseModel:
    """Create a push notification.

    Args:
        request_data (V2PostPushRequestModel): The data necessary for the notification.
        request (Request): The FastAPI request object.
        background_tasks (BackgroundTasks): The FastAPI background tasks object.

    Raises:
        HTTPException: If the template with the given template_id is not found.

    Returns:
        V2PostPushResponseModel: The notification response data.

    """
    icn = request_data.recipient_identifier.id_value
    template_id = str(request_data.template_id)
    personalization = request_data.personalisation

    try:
        template: Template = await validate_template(template_id)
    except Exception:
        # TODO: catch a more specific exception here when validate_template is implemented
        logger.info('Template not found with ID {}', template_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Undeliverable - Validation failed. Template not found with template_id {template_id}',
        )

    logger.info('Creating notification with recipent_identifier {} and template_id {}.', icn, template_id)

    notification = await dao_create_notification(Notification(personalization=json.dumps(personalization)))

    background_tasks.add_task(
        send_push_notification_helper, personalization, icn, template, request.app.enp_state.providers['aws']
    )

    logger.info(
        'Successful notification {} created with recipient_identifer {} and template_id {}.',
        notification.id,
        icn,
        template_id,
    )
    return V2PostPushResponseModel()
