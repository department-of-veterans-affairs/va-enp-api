"""The data access objects for notifications."""

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import UUID4
from sqlalchemy import Row, select

from app.constants import NotificationType
from app.db.db_init import get_read_session_with_context, metadata_legacy
from app.logging.logging_config import logger


class LegacyNotificationDao:
    """A class to handle the data access for notifications in the legacy database.

    Methods:
        get_notification: Get a Notification from the legacy database.
        persist_notification: Persist a notification to the database.
    """

    @staticmethod
    async def get_notification(id: UUID4) -> Row[Any]:
        """Get a Notification from the legacy database.

        Args:
            id (UUID4): id of the notification

        Returns:
            Row: notification table row
        """
        async with get_read_session_with_context() as session:
            legacy_notifications = metadata_legacy.tables['notifications']
            stmt = select(legacy_notifications).where(legacy_notifications.c.id == id)
            return (await session.execute(stmt)).one()

    @staticmethod
    async def persist_notification(
        *,
        template_id: UUID,
        template_version: int,
        recipient: Optional[str] = None,
        service_id: UUID,
        personalisation: Optional[Dict[str, Any]] = None,
        notification_type: NotificationType,
        api_key_id: UUID,
        key_type: str,
        created_at: Optional[str] = None,
        job_id: Optional[UUID] = None,
        job_row_number: Optional[int] = None,
        reference: Optional[str] = None,
        client_reference: Optional[str] = None,
        notification_id: Optional[UUID] = None,
        simulated: bool = False,
        created_by_id: Optional[UUID] = None,
        status: str = 'created',
        reply_to_text: Optional[str] = None,
        billable_units: Optional[int] = None,
        postage: Optional[str] = None,
        template_postage: Optional[str] = None,
        recipient_identifier: Optional[Dict[str, str]] = None,
        billing_code: Optional[str] = None,
        sms_sender_id: Optional[UUID] = None,
        callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist a notification to the database.

        This is currently a stub that logs the notification details and returns a mock notification record.
        In a real implementation, this would save to the database using SQL statements.

        Args:
            template_id: The ID of the template used
            template_version: The version of the template
            recipient: The recipient's contact information (phone/email)
            service_id: The ID of the service sending the notification
            personalisation: Template variable replacements
            notification_type: Type of notification (SMS/EMAIL)
            api_key_id: The API key ID used
            key_type: The type of API key (e.g. team, live, test)
            created_at: When the notification was created
            job_id: Optional batch job ID
            job_row_number: Row number for batch processing
            reference: Client reference
            client_reference: Alternative client reference
            notification_id: Optional pre-generated notification ID
            simulated: Whether this is a simulated notification
            created_by_id: User ID of creator
            status: Initial status for the notification
            reply_to_text: Reply-to information
            billable_units: Number of billable units
            postage: Postage information
            template_postage: Template postage information
            recipient_identifier: Recipient identifier information
            billing_code: Optional billing code
            sms_sender_id: Optional SMS sender ID
            callback_url: URL for delivery status callbacks

        Returns:
            Dict containing the created notification data
        """
        notification_id = notification_id or uuid4()

        logger.info(
            'Persisting notification: id={}, template_id={}, recipient={}, type={}, status={}',
            notification_id,
            template_id,
            recipient or 'via-identifier',
            notification_type,
            status,
        )

        # This is a stub - in the real implementation we would save to the database
        # Example:
        # async with get_write_session_with_context() as session:
        #     legacy_notifications = metadata_legacy.tables['notifications']
        #     stmt = insert(legacy_notifications).values(
        #         id=notification_id,
        #         template_id=template_id,
        #         # ...other fields
        #     )
        #     await session.execute(stmt)
        #     await session.commit()

        # Return mock notification data that would normally come from the database
        notification = {
            'id': notification_id,
            'template_id': template_id,
            'recipient': recipient,
            'notification_type': notification_type,
            'status': status,
            'reference': reference,
            'service_id': service_id,
            'personalisation': personalisation,
            'recipient_identifier': recipient_identifier,
            'template_version': template_version,
            'api_key_id': api_key_id,
            'key_type': key_type,
            'billing_code': billing_code,
            'callback_url': callback_url,
            'sms_sender_id': sms_sender_id,
        }

        return notification
