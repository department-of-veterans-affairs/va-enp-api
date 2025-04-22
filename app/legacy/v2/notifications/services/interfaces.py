"""Abstract interfaces for notification services."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import UUID4

from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel


class NotificationProcessor(ABC):
    """Abstract base class for notification processors."""

    @abstractmethod
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
        """
        pass


class SmsProcessor(NotificationProcessor):
    """Interface for SMS notification processors."""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass


class DeliveryService(ABC):
    """Abstract interface for delivery services."""

    @abstractmethod
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
        """
        pass


class SmsDeliveryService(DeliveryService):
    """Interface for SMS delivery services."""

    @abstractmethod
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
        pass


class RecipientLookupService(ABC):
    """Abstract interface for recipient lookup services."""

    @abstractmethod
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
        pass
