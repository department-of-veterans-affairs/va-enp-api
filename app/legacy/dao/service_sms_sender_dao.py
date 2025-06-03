"""The data access objects for notifications."""

from typing import Any

from loguru import logger
from pydantic import UUID4
from sqlalchemy import Row, select
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.db.db_init import get_read_session_with_context, metadata_legacy
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.utils import db_retry


class LegacyServiceSmsSenderDao:
    """A class to handle the data access for service_sms_sender data in the legacy database."""

    @staticmethod
    async def get(id: UUID4) -> Row[Any]:
        """Get a ServiceSmsSender from the legacy database.

        Args:
            id (UUID4): id of the ServiceSmsSender

        Raises:
            NonRetryableError: Unable to get the service

        Returns:
            Row[Any]: service_sms_senders table row
        """
        try:
            row: Row[Any] = await LegacyServiceSmsSenderDao._get(id)
        except (RetryableError, NonRetryableError) as e:
            # Exceeded retries or was never retryable. Downstream methods logged this
            raise NonRetryableError from e
        return row

    @staticmethod
    async def get_service_default(service_id: UUID4) -> Row[Any]:
        """Get a ServiceSmsSender from the legacy database.

        Args:
            service_id (UUID4): id of the service

        Raises:
            NonRetryableError: Unable to get the service

        Returns:
            Row[Any]: service_sms_senders table row
        """
        try:
            row: Row[Any] = await LegacyServiceSmsSenderDao._get_service_default(service_id)
        except (RetryableError, NonRetryableError) as e:
            # Exceeded retries or was never retryable. Downstream methods logged this
            raise NonRetryableError from e
        return row

    @db_retry
    @staticmethod
    async def _get(id: UUID4) -> Row[Any]:
        legacy_service_sms_senders = metadata_legacy.tables['service_sms_senders']
        try:
            stmt = select(legacy_service_sms_senders).where(legacy_service_sms_senders.c.id == id)
            async with get_read_session_with_context() as session:
                return (await session.execute(stmt)).one()

        except (IntegrityError, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception('Service lookup failed: invalid or unexpected data for id: {}', id)
            raise NonRetryableError('Service lookup failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning('Service lookup failed due to a transient database error for id: {}', id)
            raise RetryableError('Service lookup failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception('Unexpected SQLAlchemy error during service lookup for id: {}', id)
            raise NonRetryableError('Unexpected SQLAlchemy error during service lookup.') from e

    @db_retry
    @staticmethod
    async def _get_service_default(service_id: UUID4) -> Row[Any]:
        legacy_service_sms_senders = metadata_legacy.tables['service_sms_senders']
        try:
            stmt = (
                select(legacy_service_sms_senders)
                .where(legacy_service_sms_senders.c.service_id == service_id)
                .where(legacy_service_sms_senders.c.is_default)
            )
            async with get_read_session_with_context() as session:
                return (await session.execute(stmt)).one()

        except (IntegrityError, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception('Service lookup failed: invalid or unexpected data for id: {}', id)
            raise NonRetryableError('Service lookup failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning('Service lookup failed due to a transient database error for id: {}', id)
            raise RetryableError('Service lookup failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception('Unexpected SQLAlchemy error during service lookup for id: {}', id)
            raise NonRetryableError('Unexpected SQLAlchemy error during service lookup.') from e
