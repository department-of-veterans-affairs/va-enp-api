"""All endpoints for the v2/notifications route."""

import asyncio
from datetime import datetime
from typing import Annotated, Any, Callable, Coroutine, Dict
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request, status
from pydantic import UUID4
from starlette_context import context

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
) -> Dict[str, str]:
    """Handle direct SMS notification via phone number.

    Args:
        request: The SMS request model
        notification_id: Generated notification ID
        template_id: Template ID from request
        template_version: Template version
        background_tasks: FastAPI background tasks

    Returns:
        Dict[str, str]: The persisted notification data
    """
    logger.info(
        'Direct SMS notification created with recipient {} and template_id {}.',
        request.phone_number,
        template_id,
    )

    # Simulate an async operation
    await asyncio.sleep(0.01)

    # Record notification details that would be stored
    notification_data = {
        'id': str(notification_id),
        'template_id': str(template_id),
        'template_version': str(template_version),  # Convert int to string
        'recipient': str(request.phone_number),
        'timestamp': datetime.now().isoformat(),
    }

    return notification_data


async def _handle_identifier_sms_notification(
    request: V2PostSmsRequestModel,
    notification_id: UUID,
    template_id: UUID,
    template_version: int,
) -> Dict[str, str]:
    """Handle SMS notification via recipient identifier.

    Args:
        request: The SMS request model
        notification_id: Generated notification ID
        template_id: Template ID from request
        template_version: Template version

    Returns:
        Dict[str, str]: The persisted notification data
    """
    assert request.recipient_identifier is not None, 'recipient_identifier should not be None'

    recipient_id_type = request.recipient_identifier.id_type
    masked_id = f'{request.recipient_identifier.id_value[:-6]}XXXXXX'  # Do not log ICNs (PII)
    logger.info(
        'Identifier SMS notification created with recipient_identifier {} and template_id {}.',
        masked_id,
        template_id,
    )

    # Simulate an async operation, this is where we'd enqueue the celery task
    await asyncio.sleep(0.01)

    notification_data = {
        'id': str(notification_id),
        'template_id': str(template_id),
        'template_version': str(template_version),  # Convert int to string
        'recipient_identifier_type': recipient_id_type,
        'recipient_identifier_value': masked_id,  # Use masked value for logging
        'timestamp': datetime.now().isoformat(),
    }

    return notification_data


def get_sms_notification_handler(
    request: V2PostSmsRequestModel,
) -> Callable[[V2PostSmsRequestModel, UUID, UUID, int], Coroutine[Any, Any, Dict[str, str]]]:
    """Determine the appropriate SMS notification handler based on request content.

    Args:
        request: The SMS notification request model

    Returns:
        The appropriate handler function
    """
    # Our model validator guarantees exactly one of phone_number or recipient_identifier is provided
    if request.phone_number:
        return _handle_direct_sms_notification
    else:
        # At this point, mypy knows recipient_identifier cannot be None
        # because of our model validator ensuring exactly one is provided
        return _handle_identifier_sms_notification


@v2_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
@v2_legacy_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
async def create_sms_notification(
    request: Annotated[
        V2PostSmsRequestModel,
        Body(
            openapi_examples=V2PostSmsRequestModel.json_schema_extra['examples'],
        ),
    ],
    handler: Annotated[
        Callable[[V2PostSmsRequestModel, UUID, UUID, int], Coroutine[Any, Any, Dict[str, str]]],
        Depends(get_sms_notification_handler),
    ],
) -> V2PostSmsResponseModel:
    """Create an SMS notification.

    Args:
        request: The SMS notification request model
        background_tasks: FastAPI background tasks object
        handler: Injected handler function based on request content

    Returns:
        V2PostSmsResponseModel: The notification response data
    """
    logger.debug('Creating SMS notification with request data: {}', request)

    # Mock a template as if we had retrieved it
    template = {
        'id': request.template_id,
        'version': 1,
        'service_id': uuid4(),
    }
    notification_id = uuid4()
    template_version: int = 1  # Explicitly define template version with type annotation
    context['template_id'] = f'{request.template_id}:{template_version}'
    context['notification_id'] = notification_id
    context['service_id'] = template['service_id']

    try:
        await validate_template(request.template_id, NotificationType.SMS, request.personalisation)
    except ValueError as e:
        raise_request_validation_error(str(e))

    # Use the injected handler - the handlers are now async so we need to await them
    await handler(request, notification_id, request.template_id, template_version)

    return V2PostSmsResponseModel(
        id=notification_id,
        reference=request.reference,
        billing_code=request.billing_code,
        callback_url=request.callback_url,
        scheduled_for=request.scheduled_for,
        template=V2Template(
            id=request.template_id,
            uri=HttpsUrl(f'https://example.com/templates/{request.template_id}'),
            version=template_version,  # Use the explicitly typed variable instead
        ),
        uri=HttpsUrl(f'https://example.com/notifications/{notification_id}'),
        content=V2SmsContentModel(
            body='',
            from_number=ValidatedPhoneNumber('+18005550101'),  # Would be determined from sms_sender_id
        ),
    )
