"""Data Access Object for recipient identifiers in the legacy database schema."""

from pydantic import UUID4
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.utils import db_retry
from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel
from app.logging.logging_config import logger


class RecipientIdentifiersDao:
    """Data access object for recipient identifiers in the legacy database schema."""

    @staticmethod
    async def set_recipient_identifiers(
        notification_id: UUID4,
        recipient_identifiers: RecipientIdentifierModel,
    ) -> None:
        """Set recipient identifiers for a notification.

        Args:
            notification_id (UUID4): The unique identifier of the notification.
            recipient_identifiers (RecipientIdentifierModel): The recipient identifiers to set.

        Raises:
            NonRetryableError: If the failure is deterministic (e.g., bad input).
        """
        try:
            await RecipientIdentifiersDao._set_recipient_identifiers(notification_id, recipient_identifiers)
        except (RetryableError, NonRetryableError) as e:
            # Exceeded retries or was never retryable. Downstream methods logged this
            raise NonRetryableError from e

    @db_retry
    @staticmethod
    async def _set_recipient_identifiers(
        notification_id: UUID4,
        recipient_identifiers: RecipientIdentifierModel,
    ) -> None:
        """Set the recipient identifiers for a notification.

        Args:
            notification_id (UUID4): id of the notification
            recipient_identifiers (dict[str, str]): The recipient identifiers

        Raises:
            RetryableError: If a transient database error occurs
            NonRetryableError: If unable to set the recipient identifiers
        """
        legacy_recipient_identifiers = metadata_legacy.tables['recipient_identifiers']
        try:
            async with get_write_session_with_context() as session:
                stmt = insert(legacy_recipient_identifiers).values(
                    notification_id=notification_id,
                    id_type=recipient_identifiers.id_type.value,
                    id_value=recipient_identifiers.id_value,
                )
                await session.execute(stmt)
                await session.commit()

        except (IntegrityError, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception(
                'Recipient identifiers insert failed: invalid or unexpected data for id: {}', notification_id
            )
            raise NonRetryableError('Recipient identifiers insert failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning(
                'Recipient identifiers insert failed due to a transient database error for id: {}', notification_id
            )
            raise RetryableError('Recipient identifiers insert failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception(
                'Unexpected SQLAlchemy error during recipient identifiers insert for id: {}', notification_id
            )
            raise NonRetryableError('Unexpected SQLAlchemy error during recipient identifiers insert.') from e

        except Exception as e:
            logger.exception('Unexpected error during recipient identifiers insert for id: {}', notification_id)
            raise NonRetryableError('Unexpected error during recipient identifiers insert.') from e
