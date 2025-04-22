"""Service providers for dependency injection."""

from typing import Optional

from fastapi import Depends

from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel
from app.legacy.v2.notifications.services.implementations import (
    DirectPhoneNumberSmsProcessor,
    DirectRecipientIdentifierSmsProcessor,
)
from app.legacy.v2.notifications.services.interfaces import (
    NotificationProcessor,
    PhoneNumberSmsProcessor,
    RecipientIdentifierSmsProcessor,
)


def get_phone_number_sms_processor() -> PhoneNumberSmsProcessor:
    """Get a phone number SMS processor instance.

    Returns:
        A phone number SMS processor implementation.
    """
    return DirectPhoneNumberSmsProcessor()


def get_recipient_identifier_sms_processor() -> RecipientIdentifierSmsProcessor:
    """Get a recipient identifier SMS processor instance.

    Returns:
        A recipient identifier SMS processor implementation.
    """
    return DirectRecipientIdentifierSmsProcessor()


def get_sms_processor(
    phone_number: Optional[str] = None,
    recipient_identifier: Optional[RecipientIdentifierModel] = None,
    phone_number_processor: PhoneNumberSmsProcessor = Depends(get_phone_number_sms_processor),
    recipient_identifier_processor: RecipientIdentifierSmsProcessor = Depends(get_recipient_identifier_sms_processor),
) -> NotificationProcessor:
    """Get an SMS processor instance based on the provided parameters.

    This will select the appropriate processor type based on whether a phone number,
    recipient identifier, or both are provided.

    If both are provided, it prioritizes the phone number processor.

    Args:
        phone_number: The phone number if provided.
        recipient_identifier: The recipient identifier if provided.
        phone_number_processor: The phone number processor implementation.
        recipient_identifier_processor: The recipient identifier processor implementation.

    Returns:
        The appropriate SMS processor implementation.

    Raises:
        ValueError: If neither phone_number nor recipient_identifier is provided.
    """
    if phone_number is not None:
        return phone_number_processor
    elif recipient_identifier is not None:
        return recipient_identifier_processor
    else:
        # This case should not happen if validation is working correctly,
        # but we include it for completeness
        raise ValueError('Either phone_number or recipient_identifier must be provided')
