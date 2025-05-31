"""The data access objects for notifications."""

from datetime import datetime
from typing import Any

from loguru import logger
from pydantic import UUID4
from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.constants import NotificationType
from app.db.db_init import get_read_session_with_context, get_write_session_with_context, metadata_legacy
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.utils import db_retry


class LegacyNotificationDao:
    """A class to handle the data access for notifications in the legacy database.

    Methods:
        get_notification: Get a Notification from the legacy database.
    """

    @staticmethod
    async def get_notification(id: UUID4) -> Row[Any]:
        """Get a Notification from the legacy database.

        Args:
            id (UUID4): id of the notification

        Returns:
            Row: notification table row
        """
        legacy_notifications = metadata_legacy.tables['notifications']
        stmt = select(legacy_notifications).where(legacy_notifications.c.id == id)

        async with get_read_session_with_context() as session:
            return (await session.execute(stmt)).one()

    @staticmethod
    async def create_notification(
        id: UUID4,
        notification_type: NotificationType,
        template_version: int,
        billable_units: int = 0,
        key_type: str = 'normal',
    ) -> None:
        """Get a Notification from the legacy database.

        Args:
            id (UUID4): id of the notification

        Returns:
            Row: notification table row
        """
        try:
            await LegacyNotificationDao._insert_notification(**locals())
        except (RetryableError, NonRetryableError) as e:
            # Exceeded retries or was never retryable. Downstream methods logged this
            raise NonRetryableError from e

    @db_retry
    @staticmethod
    async def _insert_notification(
        id: UUID4,
        notification_type: NotificationType,
        template_version: int,
        billable_units: int,
        key_type: str,
    ) -> None:
        legacy_notifications = metadata_legacy.tables['notifications']
        try:
            async with get_write_session_with_context() as session:
                stmt = insert(legacy_notifications).values(
                    id=id,
                    notification_type=notification_type.value,
                    template_version=template_version,
                    billable_units=billable_units,
                    created_at=datetime.now(),
                    key_type=key_type,
                )
                await session.execute(stmt)
                await session.commit()
        except (IntegrityError, DataError) as e:
            if 'duplicate' in str(e).lower():
                logger.warning('Duplicate key detected: {}', id)
                raise RetryableError(log_msg='Duplicate key') from e
            else:
                # These are deterministic and will likely fail again
                logger.exception('Notification insert failed: invalid or unexpected data for id: {}', id)
                raise NonRetryableError('Notification insert failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning('Notification insert failed due to a transient database error for id: {}', id)
            raise RetryableError('Notification insert failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception('Unexpected SQLAlchemy error during notification insert for id: {}', id)
            raise NonRetryableError('Unexpected SQLAlchemy error during notification insert.') from e
