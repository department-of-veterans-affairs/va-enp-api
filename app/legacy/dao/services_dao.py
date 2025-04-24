"""The data access objects for Services."""

from datetime import datetime
from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, insert, select

from app.db.db_init import get_read_session_with_context, get_write_session_with_context, metadata_legacy


class LegacyServiceDao:
    """A class to handle the data access for services in the legacy database.

    Methods:
        get_service: Get a Service from the legacy database.
    """

    @staticmethod
    async def get_service(id: UUID4) -> Row[Any]:
        """Get a Service from the legacy database.

        Args:
            id (UUID4): id of the Service

        Returns:
            Row: services table row
        """
        async with get_read_session_with_context() as session:
            legacy_services = metadata_legacy.tables['services']
            stmt = select(legacy_services).where(legacy_services.c.id == id)
            return (await session.execute(stmt)).one()

    @staticmethod
    async def create_service(
        id: UUID4,
        name: str,
        created_at: datetime,
        active: bool,
        message_limit: int,
        restricted: bool,
        research_mode: bool,
        created_by_id: UUID4,
        prefix_sms: bool,
        rate_limit: int,
        count_as_live: bool,
        version: int,
    ) -> Row[Any]:
        """Create a Service for the legacy database.

        Args:
            id (UUID4): id of this Service
            name (str): Service name
            created_at (datetime): Time of creation
            active (bool): Is the Service active
            message_limit (int): How many messages can be sent per day
            restricted (bool): Is the Service in restricted mode
            research_mode (bool): Is the Service in research mode
            created_by_id (UUID4): User that created this Service
            prefix_sms (bool): Is there a prefix for SMS messages?
            rate_limit (int): Maximum rate of notifications per 60 seconds
            count_as_live (bool): Deprecated - unused in notification-api
            version (int): Service version

        Returns:
            Row[Any]: Object representing a Service
        """
        async with get_write_session_with_context() as session:
            legacy_services = metadata_legacy.tables['services']
            insert_stmt = insert(legacy_services).values(
                id=id,
                name=name,
                created_at=created_at,
                active=active,
                message_limit=message_limit,
                restricted=restricted,
                research_mode=research_mode,
                created_by_id=created_by_id,
                prefix_sms=prefix_sms,
                rate_limit=rate_limit,
                count_as_live=count_as_live,
                version=version,
            )
            try:
                await session.execute(insert_stmt)
                await session.commit()
            except Exception:
                raise
            select_stmt = select(legacy_services).where(legacy_services.c.id == id)
            return (await session.execute(select_stmt)).one()
