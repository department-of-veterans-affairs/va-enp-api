"""Service providers for dependency injection."""

from fastapi import BackgroundTasks, Depends

from app.legacy.v2.notifications.services.implementations import (
    BackgroundTaskRecipientLookupService,
    BackgroundTaskSmsDeliveryService,
    DefaultSmsProcessor,
)
from app.legacy.v2.notifications.services.interfaces import (
    RecipientLookupService,
    SmsDeliveryService,
    SmsProcessor,
)


def get_sms_delivery_service(
    background_tasks: BackgroundTasks,
) -> SmsDeliveryService:
    """Get an SMS delivery service instance.

    Args:
        background_tasks: The FastAPI background tasks object.

    Returns:
        An SMS delivery service implementation.
    """
    return BackgroundTaskSmsDeliveryService(background_tasks)


def get_recipient_lookup_service(
    background_tasks: BackgroundTasks,
) -> RecipientLookupService:
    """Get a recipient lookup service instance.

    Args:
        background_tasks: The FastAPI background tasks object.

    Returns:
        A recipient lookup service implementation.
    """
    return BackgroundTaskRecipientLookupService(background_tasks)


def get_sms_processor(
    delivery_service: SmsDeliveryService = Depends(get_sms_delivery_service),
    lookup_service: RecipientLookupService = Depends(get_recipient_lookup_service),
) -> SmsProcessor:
    """Get an SMS processor instance.

    Args:
        delivery_service: The service to use for SMS delivery.
        lookup_service: The service to use for recipient lookup.

    Returns:
        An SMS processor implementation.
    """
    return DefaultSmsProcessor(
        delivery_service=delivery_service,
        lookup_service=lookup_service,
    )
