"""Module for notification persistence and queue distribution."""

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from app.constants import IdentifierType, NotificationType
from app.logging.logging_config import logger


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
    In a real implementation, this would save to the database using LegacyNotificationDao.

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

    await logger.info(
        'Persisting notification: id={}, template_id={}, recipient={}, type={}, status={}',
        notification_id,
        template_id,
        recipient or 'via-identifier',
        notification_type,
        status,
    )

    # This is a stub - in the real implementation we would use LegacyNotificationDao to save to DB
    # Example: await LegacyNotificationDao.save_notification(...)

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


async def send_notification_to_queue(
    notification: Dict[str, Any],
    research_mode: bool = False,
    queue: Optional[str] = None,
    recipient_id_type: Optional[str] = None,
    sms_sender_id: Optional[UUID] = None,
) -> None:
    """Send a notification to the appropriate Celery task queue.

    This is currently a stub that logs the queue operation instead of actually sending to Celery.
    In reality, this would interact with SQS via Celery to enqueue the task.

    Args:
        notification: The notification to send
        research_mode: Whether the service is in research mode
        queue: Optional specific queue to use
        recipient_id_type: Type of recipient identifier if used
        sms_sender_id: Optional SMS sender ID
    """
    notification_type = notification.get('notification_type')
    notification_id = notification.get('id')

    # Determine which task would be called
    if notification_type == NotificationType.SMS:
        task_name = 'deliver_sms'

        # Check if the sender has rate limiting enabled
        if sms_sender_id:
            # For rate-limited senders we would use a different task
            # This is just a placeholder for the real implementation
            has_rate_limit = False
            if has_rate_limit:
                task_name = 'deliver_sms_with_rate_limiting'
    else:
        task_name = 'deliver_email'

    await logger.info(
        'Would send to {task} queue: notification_id={id}, type={type}, sms_sender_id={sender_id}',
        task=task_name,
        id=notification_id,
        type=notification_type,
        sender_id=sms_sender_id,
    )

    # In real implementation, this would be a call to Celery to enqueue the task
    # Example:
    # await celery_app.send_task(
    #     name=task_name,
    #     args=[str(notification_id)],
    #     kwargs={"sms_sender_id": str(sms_sender_id)} if sms_sender_id else {},
    #     queue=queue or NOTIFICATION_DELIVERY_QUEUE_NAME
    # )


async def send_to_queue_for_recipient_info_based_on_recipient_identifier(
    notification: Dict[str, Any],
    id_type: IdentifierType,
    id_value: str,
    communication_item_id: Optional[UUID] = None,
    onsite_enabled: bool = False,
) -> None:
    """Send a notification to the recipient lookup queue.

    This is currently a stub that logs the operation instead of actually sending to Celery.
    In reality, this would interact with SQS via Celery to enqueue the lookup task.

    Args:
        notification: The notification to send
        id_type: Type of recipient identifier
        id_value: Value of recipient identifier
        communication_item_id: Optional communication item ID
        onsite_enabled: Whether onsite notifications are enabled
    """
    notification_id = notification.get('id')
    notification_type = notification.get('notification_type')

    # Mapping of identifier types to lookup task names
    task_name_mapping = {
        IdentifierType.ICN: 'lookup_va_profile_id',
        IdentifierType.EDIPI: 'lookup_edipi',
        IdentifierType.BIRLSID: 'lookup_birlsid',
        IdentifierType.PID: 'lookup_pid',
        IdentifierType.VA_PROFILE_ID: 'lookup_va_profile_id',
    }

    # Get task name from mapping, or generate a default one if not found
    task_name = task_name_mapping.get(id_type, f'lookup_{id_type.lower()}')

    await logger.info(
        'Would send to {task} queue: notification_id={id}, id_type={id_type}, '
        'id_value={id_value}, notification_type={type}',
        task=task_name,
        id=notification_id,
        id_type=id_type,
        id_value=id_value,
        type=notification_type,
    )

    # In real implementation, this would be a call to Celery to enqueue the task
    # Example:
    # await celery_app.send_task(
    #     name=task_name,
    #     args=[
    #         str(notification_id),
    #         id_type,
    #         id_value,
    #         str(communication_item_id) if communication_item_id else None,
    #         onsite_enabled
    #     ],
    #     queue=LOOKUP_RECIPIENT_QUEUE_NAME
    # )
