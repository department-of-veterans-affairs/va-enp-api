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

        Returns:
            List[Tuple[str, str]]: List of tuples containing (queue name, task name)
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
            List[Tuple[str, str]]: List containing the queue name and task name
        """
        logger.info('Preparing task deliver_sms with notification id {}', notification_id)
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

    def __init__(self, recipient_identifier: dict[IdentifierType, str]) -> None:
        """Initialize with recipient identifier.

        Args:
            recipient_identifier (dict[IdentifierType, str]): The recipient identifier dictionary
        """
        self.recipient_identifier = recipient_identifier

    def get_tasks(self, notification_id: UUID) -> List[Tuple[str, Tuple[str, UUID]]]:
        """Get tasks for an SMS notification via recipient identifier.

        Args:
            notification_id (UUID): Generated notification ID

        Returns:
            List[Tuple[str, str]]: List of tuples containing queue names and task names
        """
        tasks = []

        # Check if any of the values in the recipient_identifier dictionary is 'VAPROFILEID'
        if IdentifierType.VA_PROFILE_ID in self.recipient_identifier:
            logger.info('Preparing task lookup_va_profile_id with notification id {}.', notification_id)
            tasks.append(
                (
                    str(QueueNames.LOOKUP_VA_PROFILE_ID),
                    (
                        'lookup_va_profile_id',
                        notification_id,
                    ),
                )
            )

        logger.info('Preparing task lookup_contact_info with notification id {}.', notification_id)
        tasks.append(
            (
                str(QueueNames.LOOKUP_CONTACT_INFO),
                (
                    'lookup_contact_info',
                    notification_id,
                ),
            )
        )

        logger.info('Preparing task deliver_sms with notification id {}', notification_id)
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
