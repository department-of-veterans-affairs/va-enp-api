"""All endpoints for the v2/notifications route."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request, status
from pydantic import UUID4
from starlette_context import context

from app.auth import JWTBearer
from app.legacy.v2.notifications.resolvers import (
    SmsTaskResolver,
    get_sms_task_resolver,
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
    ChainedDepends,
    create_notification,
    enqueue_notification_tasks,
    send_push_notification_helper,
    validate_template,
    validate_template_personalisation,
)
from app.limits import DailyRateLimiter, ServiceRateLimiter
from app.logging.logging_config import logger
from app.routers import LegacyTimedAPIRoute

v2_legacy_notification_router = APIRouter(
    dependencies=[Depends(ChainedDepends(JWTBearer(), ServiceRateLimiter(), DailyRateLimiter()))],
    prefix='/legacy/v2/notifications',
    route_class=LegacyTimedAPIRoute,
    tags=['v2 Legacy Notification Endpoints'],
)


v2_notification_router = APIRouter(
    dependencies=[Depends(ChainedDepends(JWTBearer(), ServiceRateLimiter(), DailyRateLimiter()))],
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
async def legacy_notification_post_handler(
    request: Annotated[
        V2PostSmsRequestModel,
        Body(
            openapi_examples=V2PostSmsRequestModel.json_schema_extra['examples'],
        ),
    ],
    sms_task_resolver: Annotated[SmsTaskResolver, Depends(get_sms_task_resolver)],
    background_tasks: BackgroundTasks,
) -> V2PostSmsResponseModel:
    """Handler for an SMS notification.

    Args:
        request (V2PostSmsRequestModel): The SMS notification request model
        sms_task_resolver (SmsTaskResolver): Injected task resolver based on request content
        background_tasks (BackgroundTasks): The FastAPI background tasks object

    Returns:
        V2PostSmsResponseModel: The notification response data
    """
    # Separate the middleware from the handler/response, makes testing much simpler
    return await _sms_post(request, sms_task_resolver, background_tasks)


async def _sms_post(
    request: V2PostSmsRequestModel,
    sms_task_resolver: SmsTaskResolver,
    background_tasks: BackgroundTasks,
) -> V2PostSmsResponseModel:
    """Handler for an SMS notification.

    Args:
        request (V2PostSmsRequestModel): The SMS notification request model
        sms_task_resolver (SmsTaskResolver): Injected task resolver based on request content
        background_tasks (BackgroundTasks): The FastAPI background tasks object

    Returns:
        V2PostSmsResponseModel: The notification response data
    """
    logger.debug('Creating SMS notification with request data: {}', request)
    service_id = context['service_id']
    notification_id: UUID4 = context.data['request_id']

    template_row = await validate_template(request.template_id, service_id, request.get_channel())
    validate_template_personalisation(template_row, request.personalisation)

    await create_notification(notification_id, template_row, request)

    # Get tasks for the notification using the appropriate resolver
    task_list = sms_task_resolver.get_tasks(notification_id)
    # currently get_tasks returns List[Tuple[str, Tuple[str, UUID]]], but this may need to be adjusted for other tasks?

    logger.debug('Found {} tasks to process, sending them to background process.', len(task_list))

    # create background task to enqueue the notification
    background_tasks.add_task(enqueue_notification_tasks, task_list)

    return V2PostSmsResponseModel(
        id=notification_id,
        reference=request.reference,
        billing_code=request.billing_code,
        callback_url=request.callback_url,
        scheduled_for=request.scheduled_for,
        template=V2Template(
            id=request.template_id,
            uri=HttpsUrl(f'https://mock-notify.va.gov/templates/{request.template_id}'),
        ),
        uri=HttpsUrl(f'https://mock-notify.va.gov/notifications/{notification_id}'),
        content=V2SmsContentModel(
            body='',
            from_number=ValidatedPhoneNumber('+18005550101'),  # Would be determined from sms_sender_id
        ),
    )
