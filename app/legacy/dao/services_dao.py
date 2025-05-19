"""The data access objects for services."""

from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, select

from app.db.db_init import get_read_session_with_context, metadata_legacy


class LegacyServiceDao:
    """Data access object for interacting with service records from the legacy database schema.

    Methods:
        get_service(id): Retrieve a service row by its unique identifier.
    """

    @staticmethod
    async def get_service(id: UUID4) -> Row[Any]:
        """Retrieve a single service row by its ID.

        Args:
            id (UUID4): The unique identifier of the service to retrieve.

        Returns:
            Row[Any]: A SQLAlchemy Core Row object containing the service data.

        Notes:
            - This method uses a managed read-only session.
            - The returned row is detached and safe to inspect outside the session scope.
            - This is a low-level data access method; it does not perform any business logic.
        """
        legacy_services = metadata_legacy.tables['services']

        stmt = select(legacy_services).where(legacy_services.c.id == id)

        async with get_read_session_with_context() as session:
            result = await session.execute(stmt)

        return result.one()
