"""Utilities to aid the REST Notification routes."""

import re
from typing import Any, Awaitable, Callable

from async_lru import alru_cache
from fastapi import HTTPException, Request, status
from pydantic import UUID4
from sqlalchemy import Row
from starlette_context import context

from app.constants import FIVE_MINUTES, RESPONSE_500, NotificationType
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.clients.sqs import SqsAsyncProducer
from app.legacy.dao.notifications_dao import LegacyNotificationDao
from app.legacy.dao.recipient_identifiers_dao import RecipientIdentifiersDao
from app.legacy.dao.templates_dao import LegacyTemplateDao
from app.legacy.v2.notifications.route_schema import (
    PersonalisationFileObject,
    V2PostEmailRequestModel,
    V2PostSmsRequestModel,
)
from app.logging.logging_config import logger
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_schemas import PushModel


class ChainedDepends:
    """Chains multiple FastAPI-compatible dependencies to enforce execution order."""

    def __init__(self, *dependencies: Callable[[Request], Awaitable[Any]]) -> None:
        """Initialize the ChainedDepends with a list of async dependencies.

        Args:
            *dependencies: A sequence of callables that take a Request and return an awaitable.
        """
        self._dependencies = dependencies

    async def __call__(self, request: Request) -> None:
        """Invoke each wrapped dependency in the order they were provided.

        Each dependency must be an async callable that accepts a `Request` and returns an awaitable.
        Exceptions raised by any dependency will interrupt the chain and propagate.

        Args:
            request (Request): The incoming FastAPI request object.
        """
        for dep in self._dependencies:
            await dep(request)


async def send_push_notification_helper(
    personalization: dict[str, str | int | float] | None,
    recipient_identifier: str,
    message: str,
    provider: ProviderAWS,
) -> None:
    """Send push notification in the background.

    Args:
        personalization (dict[str, str] | None): The personalization data from the request
        recipient_identifier (str): The recipient's identifier from the request
        message (str): The placeholder message to use for the notification's message
        provider (ProviderAWS): The provider to use for sending the notification

    """
    if isinstance(personalization, dict):
        for key, value in personalization.items():
            message = message.replace(f'(({key}))', str(value))
    target_arn = await get_arn_from_icn(recipient_identifier)
    push_model = PushModel(message=message, target_arn=target_arn)

    try:
        await provider.send_notification(push_model)
    except (
        RetryableError,
        NonRetryableError,
    ) as error:
        # when these are raised we want to set the message | include status reason and log message
        logger.exception(
            'Failed to send notification for recipient_identifier {}: {}', recipient_identifier, str(error)
        )


async def get_arn_from_icn(icn: str) -> str:
    """Future method to get ARN from ICN from VAProfile.

    Args:
        icn (str): Recipient's ICN Value

    """
    raise NotImplementedError('get_arn_from_icn has not been implemented.')


async def validate_push_template(template_id: UUID4) -> None:
    """Future method to validate the template.

    Args:
        template_id (UUID4): The template ID to validate

    Raises:
        NotImplementedError: For now, raise an exception. Change the type when implemented.

    """
    # call dao to get template
    # return the template if it exists for given service, else raise an exception
    raise NotImplementedError('validate_push_template has not been implemented.')


@alru_cache(maxsize=1024, ttl=FIVE_MINUTES)
async def validate_template(
    template_id: UUID4,
    service_id: UUID4,
    expected_type: NotificationType,
) -> Row[Any]:
    """Validates the template with the given ID.

    Checks for the template in the database, that it's the right type, and is active. Raises a ValueError if any
    of these conditions are not met.

    Args:
        template_id (UUID4): The template_id to validate
        service_id (UUID4): The service_id to validate
        expected_type (NotificationType): The expected type of the template

    Returns:
        Row[Any]: A template row

    Raises:
        HTTPException: If the template is not found, not of the expected type, or archived.
    """
    try:
        template = await LegacyTemplateDao.get_by_id_and_service_id(template_id, service_id)
    except NonRetryableError:
        logger.exception('Template not found with ID {}', template_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Template not found',
        )

    try:
        _validate_template_type(template.template_type, expected_type, template_id)
        _validate_template_active(template.archived, template_id)
    except NonRetryableError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.log_msg),
        ) from e
    return template


async def create_notification(
    id: UUID4,
    template_row: Row[Any],
    request: V2PostSmsRequestModel | V2PostEmailRequestModel,
) -> None:
    """Utility function to help the route create a notification using LegacyNotificationDao.create_notification.

    Args:
        id (UUID4): notification id to use
        template_row (Row[Any]): Row of template data
        request (V2PostSmsRequestModel | V2PostEmailRequestModel): The request data

    Raises:
        HTTPException: Unexpected 5xx catch

    """
    try:
        await LegacyNotificationDao.create_notification(
            id=id,
            notification_type=request.get_channel(),
            to=request.get_direct_contact_info(),
            reply_to_text=await request.get_reply_to_text(),
            service_id=context['service_id'],
            api_key_id=context['api_key_id'],
            reference=request.reference,
            template_id=template_row.id,
            template_version=template_row.version,
            personalisation=request.personalisation,
        )

        if request.recipient_identifier:
            # If recipient identifiers are provided, set them
            await RecipientIdentifiersDao.set_recipient_identifiers(
                notification_id=id,
                recipient_identifiers=request.recipient_identifier,
            )
    except NonRetryableError as e:
        logger.exception('Failed to create notification due to unexpected error in the database')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=RESPONSE_500) from e


def _validate_template_type(
    template_type: NotificationType,
    expected_type: NotificationType,
    template_id: UUID4,
) -> None:
    """Validates that the template is of the expected type.

    Args:
        template_type (NotificationType): The template type to validate
        expected_type (NotificationType): The expected type of the template
        template_id (UUID4): The ID of the template

    Raises:
        NonRetryableError: If the template is not of the expected type
    """
    if template_type != expected_type:
        logger.warning(
            'Attempted to use a {} template for a {} notification. Template {}',
            template_type,
            expected_type,
            template_id,
        )
        raise NonRetryableError(f'{template_type} template is not suitable for {expected_type} notification')


def _validate_template_active(archived: bool, template_id: UUID4) -> None:
    """Validates that the template is active.

    Args:
        archived (bool): The archived status of the template
        template_id (UUID4): The ID of the template

    Raises:
        NonRetryableError: If the template is archived (not active)

    """
    if archived:
        logger.warning('Attempted to send using an archived template. Template {}', template_id)
        raise NonRetryableError('Template has been deleted')


def validate_template_personalisation(
    template: Row[Any],
    personalisation: dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None,
) -> None:
    """Validates the personalisation data against the template.

    Args:
        template (Row[Any]): Template row data to validate against
        personalisation (dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None): The personalisation data to validate

    Raises:
        HTTPException: If there are missing personalisation fields required by the template.

    """
    template_personalisation_fields = _collect_personalisation_from_template(template.content)
    incoming_personalisation_fields = set(personalisation.keys() if personalisation else [])

    # the current implementation is case-insensitive, so all fields are converted to lowercase
    template_personalisation_fields = set(field.lower() for field in template_personalisation_fields)
    incoming_personalisation_fields = set(field.lower() for field in incoming_personalisation_fields)

    missing_fields = template_personalisation_fields - incoming_personalisation_fields
    if missing_fields:
        logger.warning(
            'Attempted to send with temaplate {} while missing personalisation field(s): {}',
            template.id,
            missing_fields,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Missing personalisation: {", ".join(missing_fields)}',
        )


def _collect_personalisation_from_template(template_content: str) -> set[str]:
    """Collects the personalisation keys from the template.

    Args:
        template_content (str): The template content to collect personalisation keys from

    Returns:
        set[str]: The personalisation keys from the template

    """
    # personalisation keys are wrapped in double parentheses. ((example))
    pattern = r'\(\((.*?)\)\)'

    matches = re.findall(pattern, template_content)
    return set(matches)


async def enqueue_notification_tasks(tasks: list[tuple[str, tuple[str, UUID4]]]) -> None:
    """Uses the SqsAsyncProducer to enqueue tasks for processing by Celery.

    Args:
        tasks (list[tuple[str, tuple[str, UUID4]]]): The tasks to enqueue

    """
    sqs_producer = SqsAsyncProducer()

    # Does not raise an exception on failure, expect the notification to "replay" after 24.25 hours.
    # This mechanism is run on a cron schedule.
    await sqs_producer.enqueue_message(tasks)
