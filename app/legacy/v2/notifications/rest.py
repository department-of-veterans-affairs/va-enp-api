"""All endpoints for the v2/notifications route."""

import asyncio
from typing import Annotated, List, Tuple
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request, status
from pydantic import UUID4
from starlette_context import context

from app.auth import JWTBearer
from app.constants import NotificationType
from app.legacy.v2.notifications.handlers import (
    DirectSmsTaskResolver,
    IdentifierSmsTaskResolver,
    SmsTaskResolver,
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


def get_sms_task_resolver(request: V2PostSmsRequestModel) -> SmsTaskResolver:
    """Determine the appropriate SMS task resolver based on request content.

    Args:
        request (V2PostSmsRequestModel): The SMS notification request model

    Returns:
        SmsTaskResolver: The appropriate task resolver implementation
    """
    # Our model validator guarantees exactly one of phone_number or recipient_identifier is provided
    if request.phone_number:
        return DirectSmsTaskResolver(phone_number=request.phone_number)
    else:
        # At this point, we know recipient_identifier cannot be None
        # because of our model validator ensuring exactly one is provided
        assert request.recipient_identifier is not None
        return IdentifierSmsTaskResolver(recipient_identifier=request.recipient_identifier.model_dump())


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
    """Create an SMS notification.

    Args:
        request (V2PostSmsRequestModel): The SMS notification request model
        sms_task_resolver (SmsTaskResolver): Injected task resolver based on request content
        background_tasks (BackgroundTasks): The FastAPI background tasks object

    Returns:
        V2PostSmsResponseModel: The notification response data
    """
    logger.debug('Creating SMS notification with request data: {}', request)

    notification_id = uuid4()
    service_id = uuid4()

    context['template_id'] = f'{request.template_id}:{request.template_version}'
    context['notification_id'] = notification_id
    context['service_id'] = service_id

    try:
        await validate_template(
            request.template_id, request.template_version, NotificationType.SMS, request.personalisation
        )
    except ValueError as e:
        raise_request_validation_error(str(e))

    # Get tasks for the notification using the appropriate resolver
    tasks = sms_task_resolver.get_tasks(notification_id)

    # Add the background task to process the tasks
    background_tasks.add_task(process_tasks_helper, tasks)
    logger.info('Background task added to process {} tasks', len(tasks))

    return V2PostSmsResponseModel(
        id=notification_id,
        reference=request.reference,
        billing_code=request.billing_code,
        callback_url=request.callback_url,
        scheduled_for=request.scheduled_for,
        template=V2Template(
            id=request.template_id,
            uri=HttpsUrl(f'https://example.com/templates/{request.template_id}'),
            version=request.template_version,
        ),
        uri=HttpsUrl(f'https://example.com/notifications/{notification_id}'),
        content=V2SmsContentModel(
            body='',
            from_number=ValidatedPhoneNumber('+18005550101'),  # Would be determined from sms_sender_id
        ),
    )


async def process_tasks_helper(tasks: List[Tuple[str, str]]) -> None:
    """Process the list of tasks in the background.

    This helper function logs the tasks that would be processed but doesn't actually execute them.

    Args:
        tasks (List[Tuple[str, str]]): List of tuples containing queue name and task name
    """
    logger.info('Starting background processing of {} tasks', len(tasks))
    await asyncio.sleep(0.1)

    for queue_name, task_name in tasks:
        logger.info("Processing task '{}' from queue '{}'", task_name, queue_name)
        # In a real implementation, this is where we would actually send the task to the queue
        logger.info("Task '{}' would be processed here if this wasn't a simulation", task_name)

    logger.info('Completed background processing of tasks')
