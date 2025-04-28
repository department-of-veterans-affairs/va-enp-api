"""Handlers for processing notification requests."""

import asyncio
from abc import ABC, abstractmethod
from typing import TypedDict
from uuid import UUID

from app.logging.logging_config import logger


class NotificationRecord(TypedDict, total=False):
    """Type definition for notification records."""

    id: str
    template_id: str
    template_version: str
    recipient_identifier_type: str
    recipient_identifier_value: str
    recipient: str  # Add this field for direct SMS notifications
    status: str
    timestamp: str
    reason: str
    phone_number: str


class SmsNotificationHandler(ABC):
    """Abstract base class for handling SMS notifications."""

    @abstractmethod
    async def process(self, notification_id: UUID) -> None:
        """Process the notification request.

        Args:
            notification_id (UUID): The generated notification ID
        """
        pass


class DirectSmsNotificationHandler(SmsNotificationHandler):
    """Handler for direct SMS notifications via phone number."""

    def __init__(self, phone_number: str) -> None:
        """Initialize with recipient phone number.

        Args:
            phone_number (str): The recipient's phone number
        """
        self.phone_number = phone_number

    async def process(self, notification_id: UUID) -> None:
        """Process a direct SMS notification.

        Args:
            notification_id (UUID): Generated notification ID
        """
        logger.info('Calling celery task deliver_sms with notification id {}', notification_id)

        # Simulate an async operation
        await asyncio.sleep(0.01)


class IdentifierSmsNotificationHandler(SmsNotificationHandler):
    """Handler for SMS notifications via recipient identifier."""

    def __init__(self, recipient_identifier: dict) -> None:
        """Initialize with recipient identifier.

        Args:
            recipient_identifier (dict): The recipient identifier dictionary
        """
        self.recipient_identifier = recipient_identifier

    async def process(self, notification_id: UUID) -> None:
        """Process an SMS notification via recipient identifier.

        Args:
            notification_id (UUID): Generated notification ID
        """
        logger.info('Calling celery task lookup_va_profile_id with notification id {}.', notification_id)
        await asyncio.sleep(0.01)

        logger.info('Calling celery task deliver_sms with notification id {}', notification_id)
        await asyncio.sleep(0.01)