"""All endpoints for the v2/notifications route."""

import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import UUID4

from app.auth import JWTBearer
from app.constants import PhoneNumberE164
from app.dao.notifications_dao import dao_create_notification, dao_get_legacy_notification
from app.db.models import Notification, Template
from app.legacy.v2.notifications.route_schema import (
    HttpsUrl,
    V2GetNotificationResponseModel,
    V2PostPushRequestModel,
    V2PostPushResponseModel,
    V2PostSmsRequestModel,
    V2PostSmsResponseModel,
    V2SmsContentModel,
    V2Template,
)
from app.legacy.v2.notifications.utils import send_push_notification_helper, validate_template
from app.routers import TimedAPIRoute

v2_legacy_notification_router = APIRouter(
    # dependencies=[Depends(JWTBearer())],
    prefix='/legacy/v2/notifications',
    route_class=TimedAPIRoute,
    tags=['v2 Legacy Notification Endpoints'],
)


v2_notification_router = APIRouter(
    dependencies=[Depends(JWTBearer())],
    prefix='/v2/notifications',
    route_class=TimedAPIRoute,
    tags=['v2 Notification Endpoints'],
)


@v2_legacy_notification_router.post('/push', status_code=status.HTTP_201_CREATED)
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


@v2_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
@v2_legacy_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
async def create_sms_notification(
    request: Annotated[
        V2PostSmsRequestModel,
        Body(
            openapi_examples=V2PostSmsRequestModel.json_schema_extra['examples'],
        ),
    ],
) -> V2PostSmsResponseModel:
    """Create an SMS notification.

    Args:
        request_data (V2PostSmsRequestModel): The data necessary for the notification.
        request (Request): The FastAPI request object.

    Returns:
        V2PostSmsResponseModel: The notification response data.

    """
    logger.debug('Creating SMS notification with request data {}.', request)
    return V2PostSmsResponseModel(
        id=uuid4(),
        billing_code='123456',
        callback_url=HttpsUrl('https://example.com'),
        reference='123456',
        template=V2Template(
            id=uuid4(),
            uri=HttpsUrl('https://example.com'),
            version=1,
        ),
        uri=HttpsUrl('https://example.com'),
        content=V2SmsContentModel(
            body='example',
            from_number=PhoneNumberE164('+18005550101'),
        ),
    )


@v2_legacy_notification_router.get(
    '/{notification_id}',
    status_code=status.HTTP_200_OK,
)
async def get_notification(notification_id: UUID4) -> V2GetNotificationResponseModel:
    """Get a notification.

    Args:
        notification_id (UUID4): The notification to get
        db_session (async_scoped_session): The database session

    Raises:
        HTTPException: If the notification is not found

    Returns:
        V2GetNotificationResponseModel: The notification

    """
    notification = await dao_get_legacy_notification(notification_id)

    return V2GetNotificationResponseModel(
        id=notification.id,
        billing_code=notification.billing_code,
        callback_url=notification.callback_url,
        cost_in_millicents=notification.cost_in_millicents,
        created_at=notification.created_at,
        created_by_name=notification.created_by_id,
        reference=notification.reference,
        segments_count=notification.segments_count,
        sent_at=notification.sent_at,
        sent_by=notification.sent_by,
        status=notification.notification_status,
        status_reason=notification.status_reason,
        template=V2Template(
            id=notification.template_id,
            version=notification.template_version,
        ),
        type=notification.notification_type,
    )
