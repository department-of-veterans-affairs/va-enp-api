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
        phone_number: Optional[str] = None,
        recipient_identifier: Optional[RecipientIdentifierModel] = None,
        personalisation: Optional[Dict[str, Any]] = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Process a notification.

        Args:
            notification_id: The ID of the notification.
            template_id: The ID of the template to use.
            phone_number: Optional phone number for direct SMS notifications.
            recipient_identifier: Optional recipient identifier for notifications requiring lookup.
            personalisation: Template personalization data.
            **kwargs: Additional processor-specific arguments.
        """
        pass


class PhoneNumberSmsProcessor(NotificationProcessor):
    """Processor for SMS notifications sent directly to phone numbers."""

    @abstractmethod
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
        """
        pass


class RecipientIdentifierSmsProcessor(NotificationProcessor):
    """Processor for SMS notifications sent to recipients identified by an ID."""

    @abstractmethod
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
        """
        pass
