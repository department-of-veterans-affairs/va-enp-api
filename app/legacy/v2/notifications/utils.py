"""Utilities to aid the REST Notification routes."""

import re
from typing import Any, Callable, Coroutine, Sequence

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import UUID4
from sqlalchemy.exc import NoResultFound

from app.constants import NotificationType
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.templates_dao import LegacyTemplateDao
from app.legacy.v2.notifications.route_schema import PersonalisationFileObject
from app.logging.logging_config import logger
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_schemas import PushModel


def chained_depends(*deps: Callable[[Request], Coroutine[Any, Any, None]]) -> Depends:
    """Compose multiple async dependency callables into one, enforcing strict execution order.

    Each dependency must be an async function that accepts a Request and optionally raises.

    Args:
        *deps: A sequence of dependency callables to chain.

    Returns:
        Depends: A FastAPI Depends object wrapping a single callable that invokes each dependency in order.
    """

    async def wrapper(request: Request) -> None:
        for dep in deps:
            await dep(request)

    return Depends(wrapper)


def raise_request_validation_error(
    message: str,
    loc: Sequence[str] = ('body',),
) -> None:
    """Raise a FastAPI-style RequestValidationError with a message and optional location.

    Args:
        message (str): The error message.
        loc (Sequence[str]): A sequence of strings describing the field path.

    Raises:
        RequestValidationError: Handled by router to return properly structured JSON
    """
    error = {'loc': loc, 'msg': message, 'type': 'value_error'}

    raise RequestValidationError(errors=[error])


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


async def validate_template(
    template_id: UUID4,
    expected_type: NotificationType,
    personalisation: dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None,
) -> None:
    """Validates the template with the given ID.

    Checks for the template in the database, that it's the right type, and is active. Raises a ValueError if any
    of these conditions are not met.

    Args:
        template_id (UUID4): The template_id to validate
        expected_type (NotificationType): The expected type of the template
        personalisation (dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None):
            The personalisation data to validate

    Raises:
        ValueError: If the template is not found, or is invalid based on the expected type,
            personalisation is missing, or is archived.
    """
    try:
        template = await LegacyTemplateDao.get_template(template_id)
    except NoResultFound:
        logger.exception('Template not found with ID {}', template_id)
        raise ValueError('Template not found')

    try:
        _validate_template_type(template.template_type, expected_type, template_id)
        _validate_template_active(template.archived, template_id)
        _validate_template_personalisation(template.content, personalisation, template_id)
    except ValueError:
        raise


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
        ValueError: If the template is not of the expected type
    """
    if template_type != expected_type:
        logger.warning(
            'Attempted to use a {} template for a {} notification. Template {}',
            template_type,
            expected_type,
            template_id,
        )
        raise ValueError(f'{template_type} template is not suitable for {expected_type} notification')


def _validate_template_active(archived: bool, template_id: UUID4) -> None:
    """Validates that the template is active.

    Args:
        archived (bool): The archived status of the template
        template_id (UUID4): The ID of the template

    Raises:
        ValueError: If the template is archived (not active)

    """
    if archived:
        logger.warning('Attempted to send using an archived template. Template {}', template_id)
        raise ValueError('Template is not active')


def _validate_template_personalisation(
    template_content: str,
    personalisation: dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None,
    template_id: UUID4,
) -> None:
    """Validates the personalisation data against the template.

    Args:
        template_content (str): The template to validate against
        personalisation (dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None): The personalisation data to validate
        template_id (UUID4): The ID of the template

    Raises:
        ValueError: If there are missing personalisation fields required by the template.

    """
    template_personalisation_fields = _collect_personalisation_from_template(template_content)
    incoming_personalisation_fields = set(personalisation.keys() if personalisation else [])

    # the current implementation is case-insensitive, so all fields are converted to lowercase
    template_personalisation_fields = set(field.lower() for field in template_personalisation_fields)
    incoming_personalisation_fields = set(field.lower() for field in incoming_personalisation_fields)

    missing_fields = template_personalisation_fields - incoming_personalisation_fields
    if missing_fields:
        logger.warning(
            'Attempted to send with temaplate {} while missing personalisation field(s): {}',
            template_id,
            missing_fields,
        )
        raise ValueError(f'Missing personalisation: {", ".join(missing_fields)}')


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
