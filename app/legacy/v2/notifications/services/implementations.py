"""Concrete implementations of notification service interfaces."""

from typing import Any, Dict, Optional

from pydantic import UUID4

from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel
from app.legacy.v2.notifications.services.interfaces import (
    PhoneNumberSmsProcessor,
    RecipientIdentifierSmsProcessor,
)
from app.logging.logging_config import logger


class DirectPhoneNumberSmsProcessor(PhoneNumberSmsProcessor):
    """Implementation of the PhoneNumber SMS processor that delivers SMS directly."""

    async def process(
        self,
        notification_id: UUID4,
        template_id: UUID4,
        phone_number: Optional[str] = None,
        recipient_identifier: Optional[RecipientIdentifierModel] = None,
        personalisation: Optional[Dict[str, Any]] = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Process a notification to be sent to a phone number.

        Args:
            notification_id: The ID of the notification.
            template_id: The ID of the template to use.
            phone_number: The validated phone number to send the notification to.
            recipient_identifier: Optional recipient identifier (not used by this processor).
            personalisation: Template personalization data.
            **kwargs: Additional processor-specific arguments.

        Raises:
            ValueError: If phone_number is None.
        """
        if phone_number is None:
            raise ValueError('phone_number is required for this processor')

        # Create notification record with phone number
        logger.info(
            'Creating SMS notification record with phone number {} and ID {}',
            f'xxx-xxx-{phone_number[-4:]}',
            notification_id,
        )  # Partial masking for logging

        # Process SMS delivery directly instead of using a delivery service
        await self._deliver_sms(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

        logger.info('Processed SMS notification {} for delivery', notification_id)

    async def _deliver_sms(
        self,
        notification_id: UUID4,
        phone_number: str,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Deliver an SMS notification.

        This is a placeholder method for the actual SMS delivery logic.

        Args:
            notification_id: The ID of the notification.
            phone_number: The validated phone number.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
        """
        # TODO: Implement actual SMS delivery logic
        logger.debug('Processing SMS with ID {} for delivery to {}', notification_id, f'xxx-xxx-{phone_number[-4:]}')


class DirectRecipientIdentifierSmsProcessor(RecipientIdentifierSmsProcessor):
    """Implementation of the RecipientIdentifier SMS processor that processes lookups and delivery directly."""

    async def process(
        self,
        notification_id: UUID4,
        template_id: UUID4,
        phone_number: Optional[str] = None,
        recipient_identifier: Optional[RecipientIdentifierModel] = None,
        personalisation: Optional[Dict[str, Any]] = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Process a notification to be sent to a recipient identifier.

        Args:
            notification_id: The ID of the notification.
            template_id: The ID of the template to use.
            phone_number: Optional phone number (not used by this processor).
            recipient_identifier: The recipient identifier model.
            personalisation: Template personalization data.
            **kwargs: Additional processor-specific arguments.

        Raises:
            ValueError: If recipient_identifier is None.
        """
        if recipient_identifier is None:
            raise ValueError('recipient_identifier is required for this processor')

        # Create notification record without recipient
        logger.info('Creating notification record with ID {} for recipient lookup', notification_id)

        # Log recipient identifier details
        id_type = recipient_identifier.id_type
        id_value = recipient_identifier.id_value
        logger.debug('Looking up recipient with identifier type: {}, value: {}', id_type, id_value)

        # Perform lookup directly
        await self._lookup_recipient_and_send(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )

    async def _lookup_recipient_and_send(
        self,
        notification_id: UUID4,
        recipient_identifier: RecipientIdentifierModel,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Look up recipient information and send the notification.

        Args:
            notification_id: The ID of the notification.
            recipient_identifier: The recipient identifier model.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
        """
        # TODO: Implement actual recipient lookup logic
        logger.debug('Processing recipient lookup for notification ID {}', notification_id)

        # After lookup, we would retrieve a phone number and send the SMS
        # This is a placeholder for the actual implementation
        logger.info('Recipient lookup completed for notification ID {}', notification_id)

        # In a real implementation, we would use the looked-up phone number
        # For now, we just log that we would send an SMS
        logger.debug('Sending SMS to recipient after lookup, notification ID: {}', notification_id)
        # TODO: Implement actual SMS delivery logic here
