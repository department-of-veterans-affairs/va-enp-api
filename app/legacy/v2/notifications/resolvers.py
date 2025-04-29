"""Handlers for processing notification requests."""

from abc import ABC, abstractmethod
from typing import List, Tuple
from uuid import UUID

from app.constants import IdentifierType, QueueNames
from app.logging.logging_config import logger


class SmsTaskResolver(ABC):
    """Abstract base class for resolving SMS notification tasks and queues."""

    @abstractmethod
    def get_tasks(self, notification_id: UUID) -> List[Tuple[str, Tuple[str, UUID]]]:
        """Get tasks for the notification request.

        Args:
            notification_id (UUID): The generated notification ID

        """


class DirectSmsTaskResolver(SmsTaskResolver):
    """Resolver for direct SMS notification tasks via phone number."""

    def __init__(self, phone_number: str) -> None:
        """Initialize with recipient phone number.

        Args:
            phone_number (str): The recipient's phone number
        """
        self.phone_number = phone_number

    def get_tasks(self, notification_id: UUID) -> List[Tuple[str, Tuple[str, UUID]]]:
        """Get tasks for a direct SMS notification.

        Args:
            notification_id (UUID): Generated notification ID

        Returns:
            List[Tuple[str, Tuple[str, UUID]]]: List containing the queue name and task name
        """
        logger.debug('Preparing task deliver_sms with notification id {}', notification_id)
        return [
            (
                str(QueueNames.SEND_SMS),
                (
                    'deliver_sms',
                    notification_id,
                ),
            )
        ]


class IdentifierSmsTaskResolver(SmsTaskResolver):
    """Resolver for SMS notification tasks via recipient identifier."""

    def __init__(self, id_type: IdentifierType, id_value: str) -> None:
        """Initialize with recipient identifier type and value.

        Args:
            id_type (IdentifierType): The type of identifier
            id_value (str): The identifier value
        """
        self.id_type = id_type
        self.id_value = id_value

    def get_tasks(self, notification_id: UUID) -> List[Tuple[str, Tuple[str, UUID]]]:
        """Get tasks for an SMS notification via recipient identifier.

        Args:
            notification_id (UUID): Generated notification ID

        Returns:
            ListList[Tuple[str, Tuple[str, UUID]]]: List of tuples containing queue names and task names
        """
        tasks = []

        # Check if identifier is not VA_PROFILE_ID
        if self.id_type != IdentifierType.VA_PROFILE_ID:
            logger.debug('Preparing task lookup_va_profile_id with notification id {}.', notification_id)
            tasks.append(
                (
                    str(QueueNames.LOOKUP_VA_PROFILE_ID),
                    (
                        'lookup_va_profile_id',
                        notification_id,
                    ),
                )
            )

        logger.debug('Preparing task lookup_contact_info with notification id {}.', notification_id)
        tasks.append(
            (
                str(QueueNames.LOOKUP_CONTACT_INFO),
                (
                    'lookup_contact_info',
                    notification_id,
                ),
            )
        )

        logger.debug('Preparing task deliver_sms with notification id {}', notification_id)
        tasks.append(
            (
                str(QueueNames.SEND_SMS),
                (
                    'deliver_sms',
                    notification_id,
                ),
            )
        )

        return tasks
