"""All endpoints for the v2/notifications route."""

import asyncio
from datetime import datetime
from typing import Annotated, Any, Callable, Coroutine, Dict, Optional, TypedDict
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request, status
from pydantic import UUID4
from starlette_context import context

from app.auth import JWTBearer
from app.clients.va_profile import get_contact_info
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


class NotificationRecord(TypedDict, total=False):
    """Type definition for notification records."""

    id: str
    template_id: str
    template_version: str
    recipient_identifier_type: str
    recipient_identifier_value: str
    recipient: str  # Add this field for direct SMS notifications
    status: str
    timestamp: str
    reason: str
    phone_number: str


async def _handle_direct_sms_notification(
    request: V2PostSmsRequestModel,
    notification_id: UUID,
    template_id: UUID,
    template_version: int,
) -> NotificationRecord:
    """Handle direct SMS notification via phone number.

    Args:
        request: The SMS request model
        notification_id: Generated notification ID
        template_id: Template ID from request
        template_version: Template version
        background_tasks: FastAPI background tasks

    Returns:
        NotificationRecord: The persisted notification data
    """
    logger.info(
        'Direct SMS notification created with recipient {} and template_id {}.',
        request.phone_number,
        template_id,
    )

    # Simulate an async operation
    await asyncio.sleep(0.01)

    # Record notification details that would be stored
    notification_data: NotificationRecord = {
        'id': str(notification_id),
        'template_id': str(template_id),
        'template_version': str(template_version),
        'recipient': str(request.phone_number),
        'timestamp': datetime.now().isoformat(),
    }

    return notification_data


async def _lookup_contact_info(recipient_id_type: str, recipient_id_value: str, masked_id: str) -> Dict[str, str]:
    """Lookup contact information for a recipient identifier.

    Args:
        recipient_id_type: Type of identifier (e.g., ICN)
        recipient_id_value: Identifier value
        masked_id: Masked identifier for logging

    Returns:
        Dict containing the contact information

    Raises:
        ValueError: If the provided identifier is invalid
        KeyError: If the user is not found
        ConnectionError: If there's an error connecting to VA Profile
    """
    logger.info('Starting contact info lookup for recipient_identifier {}', masked_id)

    try:
        # Validate identifier before proceeding
        if not recipient_id_value:
            raise ValueError('Invalid recipient identifier provided')

        # Use the VA Profile client to get contact information
        contact_info = await get_contact_info(recipient_id_type, recipient_id_value)

        # Check if user was found
        if contact_info is None:
            raise KeyError(f'User with identifier type {recipient_id_type} not found')

        return contact_info

    except Exception as e:
        # Handle any other unexpected errors
        logger.exception('Unexpected error during VA Profile lookup: {}', e)
        raise ConnectionError(f'Error connecting to VA Profile: {e!s}')


def _create_notification_record(
    notification_id: UUID,
    template_id: UUID,
    template_version: int,
    recipient_id_type: str,
    masked_id: str,
    status: str,
    **additional_data: Optional[str],
) -> NotificationRecord:
    """Create a notification record with basic and additional data.

    Args:
        notification_id: The notification UUID
        template_id: The template UUID
        template_version: Template version number
        recipient_id_type: Type of recipient identifier
        masked_id: Masked identifier value for logging/recording
        status: Status of the notification
        additional_data: Any additional fields to include in the record

    Returns:
        Dict containing the notification record data
    """
    record: NotificationRecord = {
        'id': str(notification_id),
        'template_id': str(template_id),
        'template_version': str(template_version),
        'recipient_identifier_type': recipient_id_type,
        'recipient_identifier_value': masked_id,
        'status': status,
        'timestamp': datetime.now().isoformat(),
    }

    # Explicitly handle all possible TypedDict fields with proper type safety
    if 'reason' in additional_data and additional_data['reason'] is not None:
        record['reason'] = str(additional_data['reason'])
    if 'phone_number' in additional_data and additional_data['phone_number'] is not None:
        record['phone_number'] = str(additional_data['phone_number'])
    if 'recipient' in additional_data and additional_data['recipient'] is not None:
        record['recipient'] = str(additional_data['recipient'])

    return record


async def _handle_identifier_sms_notification(
    request: V2PostSmsRequestModel,
    notification_id: UUID,
    template_id: UUID,
    template_version: int,
) -> NotificationRecord:
    """Handle SMS notification via recipient identifier.

    Args:
        request: The SMS request model
        notification_id: Generated notification ID
        template_id: Template ID from request
        template_version: Template version

    Returns:
        NotificationRecord: The persisted notification data
    """
    assert request.recipient_identifier is not None, 'recipient_identifier should not be None'

    recipient_id_type = request.recipient_identifier.id_type
    recipient_id_value = request.recipient_identifier.id_value
    masked_id = f'{recipient_id_value[:-6]}XXXXXX'  # Do not log ICNs (PII)

    logger.info(
        'Identifier SMS notification created with recipient_identifier {} and template_id {}.',
        masked_id,
        template_id,
    )

    # Process the notification
    try:
        # Lookup contact info
        contact_info = await _lookup_contact_info(recipient_id_type, recipient_id_value, masked_id)

        # Get phone number - explicitly check for empty string vs None
        phone_number = contact_info.get('phone_number')

        if phone_number == '':
            # Empty phone number found in profile
            logger.warning('Empty phone number found in VA Profile for recipient_identifier {}', masked_id)
            return _create_notification_record(
                notification_id,
                template_id,
                template_version,
                recipient_id_type,
                masked_id,
                'failed',
                reason='no_phone_number',
            )

        # If phone_number is None, we'll handle it differently from empty string
        # Create masked version for logs
        if phone_number is None:
            masked_phone = 'UNKNOWN'
        else:
            masked_phone = f'+1XXXXXXX{phone_number[-4:]}'  # Mask all but last 4 digits

        logger.info(
            'Sending SMS to phone number {} for recipient_identifier {}',
            masked_phone,
            masked_id,
        )

        # Simulate processing delay
        await asyncio.sleep(0.1)

        # Record successful notification
        return _create_notification_record(
            notification_id,
            template_id,
            template_version,
            recipient_id_type,
            masked_id,
            'delivered',
            phone_number=masked_phone,  # Only store masked phone number in logs
        )

    except Exception as e:
        # Handle failures in the lookup process
        logger.exception('Error in contact info lookup for recipient_identifier {}: {}', masked_id, e)
        return _create_notification_record(
            notification_id,
            template_id,
            template_version,
            recipient_id_type,
            masked_id,
            'failed',
            reason=f'lookup_error: {e!s}',
        )


def get_sms_notification_handler(
    request: V2PostSmsRequestModel,
) -> Callable[[V2PostSmsRequestModel, UUID, UUID, int], Coroutine[Any, Any, NotificationRecord]]:
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
        Callable[[V2PostSmsRequestModel, UUID, UUID, int], Coroutine[Any, Any, NotificationRecord]],
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
