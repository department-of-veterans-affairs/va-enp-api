"""The data access objects for templates."""

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


class LegacyTemplateDao:
    """A class to handle the data access for templates in the legacy database.

    Methods:
        get_template_for_service: Get a Template from the legacy database for a specific service.
        get_template: Get a Template from the legacy database.
    """

    # TODO 134 - Add caching here.
    # 5 minutes TTL cache for templates
    async def get_template_for_service(template_id: UUID4, service_id: UUID4) -> Row[Any]:
        """Get a Template from the legacy database for a specific service.

        Args:
            template_id (UUID4): The unique identifier of the template.
            service_id (UUID4): The unique identifier of the service.

        Returns:
            Row[Any]: A SQLAlchemy Core Row object containing the template data.

        Raises:
            RetryableError: If the failure is likely transient (e.g., connection error).
            NonRetryableError: If the failure is deterministic (e.g., not found, bad input).
        """
        legacy_templates = metadata_legacy.tables['templates']

        stmt = select(legacy_templates).where(
            legacy_templates.c.id == template_id,
            legacy_templates.c.service_id == service_id,
        )

        try:
            async with get_read_session_with_context() as session:
                result = await session.execute(stmt)

            return result.one()

        except (NoResultFound, MultipleResultsFound, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception('Template lookup failed: invalid or unexpected data for template_id: {}', template_id)
            raise NonRetryableError(log_msg='Template lookup failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError):
            pass

    @staticmethod
    async def get_template(template_id: UUID4) -> Row[Any]:
        """Get a Template from the legacy database.

        Args:
            template_id (UUID4): The unique identifier of the template.

        Returns:
            Row[Any]: A SQLAlchemy Core Row object containing the template data.

        Raises:
            RetryableError: If the failure is likely transient (e.g., connection error).
            NonRetryableError: If the failure is deterministic (e.g., not found, bad input).
        """
        legacy_templates = metadata_legacy.tables['templates']

        stmt = select(legacy_templates).where(legacy_templates.c.id == template_id)

        try:
            async with get_read_session_with_context() as session:
                result = await session.execute(stmt)

            return result.one()

        except (NoResultFound, MultipleResultsFound, DataError) as e:
            # These are deterministic and will likely fail again
            logger.exception('Template lookup failed: invalid or unexpected data for template_id: {}', template_id)
            raise NonRetryableError(log_msg='Template lookup failed: invalid or unexpected data.') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            logger.warning('Template lookup failed due to a transient database error for template_id: {}', template_id)
            raise RetryableError(log_msg='Template lookup failed due to a transient database error.') from e

        except SQLAlchemyError as e:
            logger.exception('Unexpected SQLAlchemy error during template lookup for template_id: {}', template_id)
            raise NonRetryableError(log_msg='Unexpected SQLAlchemy error during template lookup.') from e
