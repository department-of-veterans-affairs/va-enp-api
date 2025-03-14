"""All endpoints for the v2/notifications route."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import UUID4

from app.auth import JWTBearer
from app.constants import NotificationType
from app.legacy.v2.notifications.route_schema import (
    HttpsUrl,
    V2PostPushRequestModel,
    V2PostPushResponseModel,
    V2PostSmsRequestModel,
    V2PostSmsResponseModel,
    V2SmsContentModel,
    V2Template,
    ValidatedPhoneNumber,
)
from app.legacy.v2.notifications.utils import send_push_notification_helper, validate_template
from app.routers import TimedAPIRoute

v2_legacy_notification_router = APIRouter(
    dependencies=[Depends(JWTBearer())],
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

    Returns:
        V2PostPushResponseModel: The notification response data.

    """
    icn = request_data.recipient_identifier.id_value
    template_id = UUID4(request_data.template_id)
    personalization = request_data.personalisation
    msg_template = 'Temporary string - Will be ((record)) from a push template ((table))'

    logger.info('Creating notification with recipent_identifier {} and template_id {}.', icn, template_id)

    background_tasks.add_task(
        send_push_notification_helper, personalization, icn, msg_template, request.app.enp_state.providers['aws']
    )

    logger.info(
        'Successful push notification created with recipient_identifer {} and template_id {}.',
        f'{icn[:-6]}XXXXXX',  # Do not log ICNs (PII)
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
        V2PostSmsResponseModel: The notification response data if notification is created successfully.

    Raises:
        HTTPException: If the template is not found, is not a SMS type, or is not active, or if the request is
            missing personalisation data.

    """
    logger.debug('Received SMS request with data: {}', request)

    try:
        await validate_template(request.template_id, NotificationType.SMS, request.personalisation)
    except ValueError as e:
        # Error details based on consistency with the flask api v2 response
        error_details = {
            'errors': [
                {
                    'error': 'BadRequestError',
                    'message': str(e),
                },
            ],
            'status_code': status.HTTP_400_BAD_REQUEST,
        }
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_details)

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
            body='example' if not request.personalisation else f'example - {request.personalisation}',
            from_number=ValidatedPhoneNumber('+18005550101'),
        ),
    )
