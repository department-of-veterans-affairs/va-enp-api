"""The data access objects for services."""

from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, select
from sqlalchemy.exc import (
    DataError,
    InterfaceError,
    MultipleResultsFound,
    NoResultFound,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.db.db_init import get_read_session_with_context, metadata_legacy
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.utils import db_retry
from app.logging.logging_config import logger


class LegacyServiceDao:
    """Data access object for interacting with service records from the legacy database schema.

    Methods:
        get_service(id): Retrieve a service row by its unique identifier.
    """

    @staticmethod
    async def get(id: UUID4) -> Row[Any]:
        """Retrieve a single service row by its ID.

        Args:
            id (UUID4): The unique identifier of the service to retrieve.

        Returns:
            Row[Any]: A SQLAlchemy Core Row object containing the service data.

        Raises:
            NonRetryableError: If the failure is deterministic (e.g., not found, bad input).
        """
        try:
            return await LegacyServiceDao._get(id)
        except (RetryableError, NonRetryableError) as e:
            # Exceeded retries or was never retryable. Downstream methods logged this
            raise NonRetryableError from e

    @db_retry
    @staticmethod
    async def _get(id: UUID4) -> Row[Any]:
        """Retryable and cached function to get a Service row.

        Args:
            id (UUID4): The service id to get

        Raises:
            NonRetryableError: If the error is non-retryable
            RetryableError: If the error is retryable

        Returns:
            Row[Any]: Service row
        """
        # Retryable and cached function to get a Service row.
        legacy_services = metadata_legacy.tables['services']
        try:
            stmt = select(legacy_services).where(legacy_services.c.id == id)
            async with get_read_session_with_context() as session:
                return (await session.execute(stmt)).one()

        except (NoResultFound, MultipleResultsFound, DataError) as e:
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
