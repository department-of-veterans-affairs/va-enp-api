"""The data access objects for services."""

from typing import Any

from loguru import logger
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


class LegacyServiceDao:
    """Data access object for interacting with service records from the legacy database schema.

    Methods:
        get_service(id): Retrieve a service row by its unique identifier.
    """

    @staticmethod
    async def get_service(service_id: UUID4) -> Row[Any]:
        """Retrieve a single service row by its ID.

        Args:
            service_id (UUID4): The unique identifier of the service to retrieve.

        Returns:
            Row[Any]: A SQLAlchemy Core Row object containing the service data.

        Raises:
            RetryableError: If the failure is likely transient (e.g., connection error).
            NonRetryableError: If the failure is deterministic (e.g., not found, bad input).
        """
        legacy_services = metadata_legacy.tables['services']

        stmt = select(legacy_services).where(legacy_services.c.id == service_id)

        try:
            async with get_read_session_with_context() as session:
                result = await session.execute(stmt)

            return result.one()

        except (NoResultFound, MultipleResultsFound, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception('Service lookup failed: invalid or unexpected data for service_id: {}', service_id)
            raise NonRetryableError('Service lookup failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning('Service lookup failed due to a transient database error for service_id: {}', service_id)
            raise RetryableError('Service lookup failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception('Unexpected SQLAlchemy error during service lookup for service_id: {}', service_id)
            raise NonRetryableError('Unexpected SQLAlchemy error during service lookup.') from e
