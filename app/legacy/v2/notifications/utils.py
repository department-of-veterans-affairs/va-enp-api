"""Utilities to aid the REST Notification routes."""

from loguru import logger

from app.db.models import Template
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_base import ProviderNonRetryableError, ProviderRetryableError
from app.providers.provider_schemas import PushModel


async def send_push_notification_helper(
    personalization: dict[str, str | int | float] | None,
    recipient_identifier: str,
    template: Template,
    provider: ProviderAWS,
) -> None:
    """Send push notification in the background.

    Args:
        personalization (dict[str, str] | None): The personalization data from the request
        recipient_identifier (str): The recipient's identifier from the request
        template (Template): The template to use for the notification's message
        provider (ProviderAWS): The provider to use for sending the notification

    """
    message = template.build_message(personalization)
    target_arn = await get_arn_from_icn(recipient_identifier)
    push_model = PushModel(message=message, target_arn=target_arn)

    try:
        await provider.send_notification(push_model)
    except (
        ProviderRetryableError,
        ProviderNonRetryableError,
    ) as error:
        # when these are raised we want to set the message | include status reason and log message
        logger.exception(
            'Failed to send notification for recipient_identifier {}: {}', recipient_identifier, str(error)
        )


async def validate_template(template_id: str) -> Template:
    """Future method to validate the template.

    Args:
        template_id (str): The template ID to validate

    Returns:
        Template: The template if it exists

    Raises:
        NotImplementedError: For now, raise an exception. Change the type when implemented.

    """
    # call dao to get template
    # return the template if it exists for given service, else raise an exception
    raise NotImplementedError('validate_template has not been implemented.')


async def get_arn_from_icn(icn: str) -> str:
    """Future method to get ARN from ICN from VAProfile.

    Args:
        icn (str): Recipient's ICN Value

    """
    raise NotImplementedError('get_arn_from_icn has not been implemented.')
