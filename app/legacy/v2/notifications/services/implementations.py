"""Concrete implementations of notification service interfaces."""

from typing import Any, Dict, Optional

from fastapi import BackgroundTasks
from pydantic import UUID4

from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel
from app.legacy.v2.notifications.services.interfaces import (
    RecipientLookupService,
    SmsDeliveryService,
    SmsProcessor,
)
from app.logging.logging_config import logger


class BackgroundTaskSmsDeliveryService(SmsDeliveryService):
    """SMS delivery service that uses FastAPI background tasks."""

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        """Initialize the SMS delivery service.

        Args:
            background_tasks: The FastAPI background tasks object.
        """
        self.background_tasks = background_tasks

    async def queue_for_delivery(
        self,
        notification_id: UUID4,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Queue a notification for delivery.

        Args:
            notification_id: The ID of the notification.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
            **kwargs: Additional service-specific arguments.

        Raises:
            ValueError: If phone_number is not provided in kwargs.
        """
        if 'phone_number' not in kwargs:
            raise ValueError('phone_number is required for SMS delivery')

        await self.queue_sms_for_delivery(
            notification_id=notification_id,
            phone_number=kwargs['phone_number'],
            template_id=template_id,
            personalisation=personalisation,
        )

    async def queue_sms_for_delivery(
        self,
        notification_id: UUID4,
        phone_number: str,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Queue an SMS notification for delivery.

        Args:
            notification_id: The ID of the notification.
            phone_number: The validated phone number.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
        """
        # TODO: Implement actual delivery queue logic
        self.background_tasks.add_task(
            self._deliver_sms,
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )
        logger.debug('SMS with ID {} queued for delivery to {}', notification_id, f'xxx-xxx-{phone_number[-4:]}')

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


class BackgroundTaskRecipientLookupService(RecipientLookupService):
    """Recipient lookup service that uses FastAPI background tasks."""

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        """Initialize the recipient lookup service.

        Args:
            background_tasks: The FastAPI background tasks object.
        """
        self.background_tasks = background_tasks

    async def queue_recipient_lookup(
        self,
        notification_id: UUID4,
        recipient_identifier: RecipientIdentifierModel,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Queue a task to look up recipient information.

        Args:
            notification_id: The ID of the notification.
            recipient_identifier: The recipient identifier model.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
        """
        id_type = recipient_identifier.id_type
        id_value = recipient_identifier.id_value

        self.background_tasks.add_task(
            self._lookup_recipient_info,
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )

        logger.info('Queued notification {} for recipient info lookup', notification_id)
        logger.debug('Recipient identifier type: {}, value: {}', id_type, id_value)

    async def _lookup_recipient_info(
        self,
        notification_id: UUID4,
        recipient_identifier: RecipientIdentifierModel,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Look up recipient information.

        This is a placeholder method for the actual recipient lookup logic.

        Args:
            notification_id: The ID of the notification.
            recipient_identifier: The recipient identifier model.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
        """
        # TODO: Implement actual recipient lookup logic
        logger.debug('Processing recipient lookup for notification ID {}', notification_id)


class DefaultSmsProcessor(SmsProcessor):
    """Default implementation of the SMS processor interface."""

    def __init__(self, delivery_service: SmsDeliveryService, lookup_service: RecipientLookupService) -> None:
        """Initialize the SMS processor.

        Args:
            delivery_service: The service to use for SMS delivery.
            lookup_service: The service to use for recipient lookup.
        """
        self.delivery_service = delivery_service
        self.lookup_service = lookup_service

    async def process(
        self,
        notification_id: UUID4,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Process a notification.

        Args:
            notification_id: The ID of the notification.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
            **kwargs: Additional processor-specific arguments.

        Raises:
            ValueError: If neither phone_number nor recipient_identifier is provided in kwargs.
        """
        if 'phone_number' in kwargs:
            await self.process_with_phone_number(
                notification_id=notification_id,
                phone_number=kwargs['phone_number'],
                template_id=template_id,
                personalisation=personalisation,
            )
        elif 'recipient_identifier' in kwargs:
            await self.process_with_recipient_identifier(
                notification_id=notification_id,
                recipient_identifier=kwargs['recipient_identifier'],
                template_id=template_id,
                personalisation=personalisation,
            )
        else:
            raise ValueError('Either phone_number or recipient_identifier must be provided')

    async def process_with_phone_number(
        self,
        notification_id: UUID4,
        phone_number: str,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Process SMS notification with a direct phone number.

        Args:
            notification_id: The ID of the notification.
            phone_number: The validated phone number.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
        """
        # Create notification record with phone number
        logger.info(
            'Creating SMS notification record with phone number {} and ID {}',
            f'xxx-xxx-{phone_number[-4:]}',
            notification_id,
        )  # Partial masking for logging

        # Send to delivery queue
        await self.delivery_service.queue_sms_for_delivery(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

        logger.info('Queued SMS notification {} for delivery', notification_id)

    async def process_with_recipient_identifier(
        self,
        notification_id: UUID4,
        recipient_identifier: RecipientIdentifierModel,
        template_id: UUID4,
        personalisation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Process SMS notification with a recipient identifier.

        Args:
            notification_id: The ID of the notification.
            recipient_identifier: The recipient identifier model.
            template_id: The ID of the template to use.
            personalisation: Template personalization data.
        """
        # Create notification record without recipient
        logger.info('Creating notification record with ID {} for recipient lookup', notification_id)

        # Queue lookup task
        await self.lookup_service.queue_recipient_lookup(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )
