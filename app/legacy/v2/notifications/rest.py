"""All endpoints for the v2/notifications route."""

from typing import Annotated, Dict, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request, status
from pydantic import UUID4
from starlette_context import context

from app.auth import JWTBearer
from app.constants import NotificationType
from app.legacy.dao.notifications_dao import LegacyNotificationDao
from app.legacy.v2.notifications.process_notifications import (
    send_notification_to_queue,
    send_to_queue_for_recipient_info_based_on_recipient_identifier,
)
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
from app.legacy.v2.notifications.utils import (
    raise_request_validation_error,
    send_push_notification_helper,
    validate_template,
)
from app.logging.logging_config import logger
from app.routers import LegacyTimedAPIRoute

v2_legacy_notification_router = APIRouter(
    dependencies=[Depends(JWTBearer())],
    prefix='/legacy/v2/notifications',
    route_class=LegacyTimedAPIRoute,
    tags=['v2 Legacy Notification Endpoints'],
)


v2_notification_router = APIRouter(
    dependencies=[Depends(JWTBearer())],
    prefix='/v2/notifications',
    route_class=LegacyTimedAPIRoute,
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


async def _handle_direct_sms_notification(
    request: V2PostSmsRequestModel,
    notification_id: UUID,
    template_id: UUID,
    template_version: int,
    background_tasks: BackgroundTasks,
) -> Dict:
    """Handle direct SMS notification via phone number.

    Args:
        request: The SMS request model
        notification_id: Generated notification ID
        template_id: Template ID from request
        template_version: Template version
        background_tasks: FastAPI background tasks

    Returns:
        Dict: The persisted notification data
    """
    # Mock service and API key IDs
    service_id = uuid4()
    api_key_id = uuid4()

    notification = await LegacyNotificationDao.persist_notification(
        notification_id=notification_id,
        template_id=template_id,
        template_version=template_version,
        recipient=request.phone_number,
        service_id=service_id,
        personalisation=request.personalisation,
        notification_type=NotificationType.SMS,
        api_key_id=api_key_id,
        key_type='team',  # Would come from actual API key
        reference=request.reference,
        billing_code=request.billing_code,
        sms_sender_id=request.sms_sender_id,
        callback_url=request.callback_url,
    )

    # Queue for delivery (unless simulated)
    if not request.phone_number.startswith('+1650555'):  # Example simulation check
        background_tasks.add_task(
            send_notification_to_queue, notification=notification, sms_sender_id=request.sms_sender_id
        )

    return notification


async def _handle_identifier_sms_notification(
    request: V2PostSmsRequestModel,
    notification_id: UUID,
    template_id: UUID,
    template_version: int,
    background_tasks: BackgroundTasks,
) -> Dict:
    """Handle SMS notification via recipient identifier.

    Args:
        request: The SMS request model
        notification_id: Generated notification ID
        template_id: Template ID from request
        template_version: Template version
        background_tasks: FastAPI background tasks

    Returns:
        Dict: The persisted notification data
    """
    # Mock service and API key IDs
    service_id = uuid4()
    api_key_id = uuid4()

    notification = await LegacyNotificationDao.persist_notification(
        notification_id=notification_id,
        template_id=template_id,
        template_version=template_version,
        service_id=service_id,
        personalisation=request.personalisation,
        notification_type=NotificationType.SMS,
        api_key_id=api_key_id,
        key_type='team',  # Would come from actual API key
        reference=request.reference,
        billing_code=request.billing_code,
        recipient_identifier={
            'id_type': request.recipient_identifier.id_type,
            'id_value': request.recipient_identifier.id_value,
        },
        callback_url=request.callback_url,
    )

    # Queue for contact info lookup
    background_tasks.add_task(
        send_to_queue_for_recipient_info_based_on_recipient_identifier,
        notification=notification,
        id_type=request.recipient_identifier.id_type,
        id_value=request.recipient_identifier.id_value,
        communication_item_id=None,  # Optional param we don't currently use
    )

    return notification


def _create_template_content(request: V2PostSmsRequestModel, validated_content: Optional[str] = None) -> str:
    """Create template content for the response.

    Args:
        request: The SMS request model
        validated_content: Optional validated content from template

    Returns:
        str: Template content
    """
    if validated_content:
        return validated_content

    if request.personalisation:
        return f'Example message with personalization: {request.personalisation}'

    return 'Example message content'


@v2_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
@v2_legacy_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
async def create_sms_notification(
    request: Annotated[
        V2PostSmsRequestModel,
        Body(
            openapi_examples=V2PostSmsRequestModel.json_schema_extra['examples'],
        ),
    ],
    background_tasks: BackgroundTasks,
    request_obj: Request,
) -> V2PostSmsResponseModel:
    """Create an SMS notification.

    This endpoint implements the SMS flow for both direct phone number and
    recipient-identifier based notifications. The flow includes:
    1. Template validation
    2. Notification persistence
    3. Enqueueing tasks for delivery or contact lookup

    Args:
        request: The SMS notification request model
        background_tasks: FastAPI background tasks object
        request_obj: FastAPI request object

    Returns:
        V2PostSmsResponseModel: The notification response data
    """
    context['template_id'] = request.template_id
    logger.debug('Creating SMS notification with request data: {}', request)

    # 1. Validate the template
    template_content = None
    try:
        template_content = await validate_template(request.template_id, NotificationType.SMS, request.personalisation)
    except ValueError as e:
        raise_request_validation_error(str(e))

    # Generate notification ID and set template version
    notification_id = uuid4()
    template_version = 1  # Would come from actual template

    # 2. Process notification based on delivery method
    if request.phone_number:
        await _handle_direct_sms_notification(
            request, notification_id, request.template_id, template_version, background_tasks
        )
    else:
        await _handle_identifier_sms_notification(
            request, notification_id, request.template_id, template_version, background_tasks
        )

    # 3. Generate content for response
    content = _create_template_content(request, template_content)

    # 4. Build and return response
    return V2PostSmsResponseModel(
        id=notification_id,
        reference=request.reference,
        billing_code=request.billing_code,
        callback_url=request.callback_url,
        scheduled_for=request.scheduled_for,
        template=V2Template(
            id=request.template_id,
            uri=HttpsUrl(f'https://example.com/templates/{request.template_id}'),
            version=template_version,
        ),
        uri=HttpsUrl(f'https://example.com/notifications/{notification_id}'),
        content=V2SmsContentModel(
            body=content,
            from_number=ValidatedPhoneNumber('+18005550101'),  # Would be determined from sms_sender_id
        ),
    )
