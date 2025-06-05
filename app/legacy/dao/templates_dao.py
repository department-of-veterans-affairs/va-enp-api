"""The data access objects for templates."""

from typing import Any

from async_lru import alru_cache
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

from app.constants import FIVE_MINUTES
from app.db.db_init import get_read_session_with_context, metadata_legacy
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.utils import db_retry
from app.logging.logging_config import logger


class LegacyTemplateDao:
    """A class to handle the data access for templates in the legacy database.

    Methods:
        get: Retrieve a single template row by its ID.
        get_by_id_and_service_id: Retrieve a single template row by its ID and service ID.
    """

    @staticmethod
    async def get(id: UUID4) -> Row[Any]:
        """Retrieve a single templaet row by its ID.

        Args:
            id (UUID4): The unique identifier of the templaet to retrieve.

        Returns:
            Row[Any]: A SQLAlchemy Core Row object containing the templaet data.

        Raises:
            NonRetryableError: If the failure is deterministic (e.g., not found, bad input).
        """
        try:
            return await LegacyTemplateDao._get(id)
        except (RetryableError, NonRetryableError) as e:
            # Exceeded retries or was never retryable. Downstream methods logged this
            raise NonRetryableError from e

    @db_retry
    @staticmethod
    async def _get(id: UUID4) -> Row[Any]:
        """Get a Template from the legacy database.

        Args:
            id (UUID4): The template id

        Raises:
            NonRetryableError: This is a non-retryable error
            RetryableError: This is a retryable error

        Returns:
            Row[Any]: Template row
        """
        legacy_templates = metadata_legacy.tables['templates']
        try:
            stmt = select(legacy_templates).where(legacy_templates.c.id == id)
            async with get_read_session_with_context() as session:
                return (await session.execute(stmt)).one()

        except (NoResultFound, MultipleResultsFound, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception('Template lookup failed: invalid or unexpected data for id: {}', id)
            raise NonRetryableError('Template lookup failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning('Template lookup failed due to a transient database error for id: {}', id)
            raise RetryableError('Template lookup failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception('Unexpected SQLAlchemy error during template lookup for id: {}', id)
            raise NonRetryableError('Unexpected SQLAlchemy error during template lookup.') from e

    @alru_cache(maxsize=1024, ttl=FIVE_MINUTES)
    @staticmethod
    async def get_by_id_and_service_id(id: UUID4, service_id: UUID4) -> Row[Any]:
        """Retrieve a single template row by its ID and service ID.

        Args:
            id (UUID4): The unique identifier of the template to retrieve.
            service_id (UUID4): The service ID that owns the template.

        Returns:
            Row[Any]: A SQLAlchemy Core Row object containing the template data.

        Raises:
            NonRetryableError: If the failure is deterministic (e.g., not found, bad input).
        """
        try:
            return await LegacyTemplateDao._get_by_id_and_service_id(id, service_id)
        except (RetryableError, NonRetryableError) as e:
            # Exceeded retries or was never retryable. Downstream methods logged this
            raise NonRetryableError from e

    @db_retry
    @staticmethod
    async def _get_by_id_and_service_id(id: UUID4, service_id: UUID4) -> Row[Any]:
        """Get a Template from the legacy database by ID and service ID.

        Args:
            id (UUID4): The template id
            service_id (UUID4): The service id that owns the template

        Raises:
            NonRetryableError: This is a non-retryable error
            RetryableError: This is a retryable error

        Returns:
            Row[Any]: Template row
        """
        legacy_templates = metadata_legacy.tables['templates']
        try:
            stmt = select(legacy_templates).where(
                legacy_templates.c.id == id, legacy_templates.c.service_id == service_id
            )
            async with get_read_session_with_context() as session:
                return (await session.execute(stmt)).one()

        except (NoResultFound, MultipleResultsFound, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception(
                'Template lookup failed: invalid or unexpected data for id: {} and service_id: {}', id, service_id
            )
            raise NonRetryableError('Template lookup failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning(
                'Template lookup failed due to a transient database error for id: {} and service_id: {}', id, service_id
            )
            raise RetryableError('Template lookup failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception(
                'Unexpected SQLAlchemy error during template lookup for id: {} and service_id: {}', id, service_id
            )
            raise NonRetryableError('Unexpected SQLAlchemy error during template lookup.') from e
