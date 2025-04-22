"""All endpoints for the v2/notifications route."""

from typing import Annotated
from uuid import uuid4

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
from app.legacy.v2.notifications.services.interfaces import SmsProcessor
from app.legacy.v2.notifications.services.providers import get_sms_processor
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


@v2_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
@v2_legacy_notification_router.post('/sms', status_code=status.HTTP_201_CREATED)
async def create_sms_notification(
    request: Annotated[
        V2PostSmsRequestModel,
        Body(
            openapi_examples=V2PostSmsRequestModel.json_schema_extra['examples'],
        ),
    ],
    sms_processor: Annotated[SmsProcessor, Depends(get_sms_processor)],
) -> V2PostSmsResponseModel:
    """Create an SMS notification.

    Args:
        request (V2PostSmsRequestModel): The data necessary for the notification.
        sms_processor (SmsProcessor): The SMS processor service.

    Returns:
        V2PostSmsResponseModel: The notification response data if notification is created successfully.
    """
    # Extract form data and set context
    context['template_id'] = str(request.template_id)
    logger.debug('Received SMS request with data: {}', request)

    # Validate SMS sender and template
    try:
        await validate_template(request.template_id, NotificationType.SMS, request.personalisation)
    except ValueError as e:
        raise_request_validation_error(str(e))

    # Generate notification ID
    notification_id = uuid4()
    logger.info('Creating notification with ID {} and template_id {}.', notification_id, request.template_id)

    # Process the notification using the appropriate method based on the request data
    process_kwargs = {}
    if request.phone_number is not None:
        process_kwargs['phone_number'] = request.phone_number
    if request.recipient_identifier is not None:
        process_kwargs['recipient_identifier'] = request.recipient_identifier  # type: ignore[assignment]

    await sms_processor.process(
        notification_id=notification_id,
        template_id=request.template_id,
        personalisation=request.personalisation,
        **process_kwargs,
    )

    # Return response with notification details
    return V2PostSmsResponseModel(
        id=notification_id,
        billing_code=request.billing_code,
        callback_url=request.callback_url,
        reference=request.reference,
        template=V2Template(
            id=request.template_id,
            uri=HttpsUrl(f'https://example.com/templates/{request.template_id}'),
            version=1,
        ),
        uri=HttpsUrl(f'https://example.com/notifications/{notification_id}'),
        content=V2SmsContentModel(
            body='example' if not request.personalisation else f'example - {request.personalisation}',
            from_number=ValidatedPhoneNumber('+18005550101'),
        ),
    )
