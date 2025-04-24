"""The data access objects for API Keys."""

from datetime import datetime
from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, insert, select

from app.db.db_init import get_read_session_with_context, get_write_session_with_context, metadata_legacy


class LegacyApiKeyDao:
    """A class to handle the data access for api_keys in the legacy database."""

    NORMAL_TYPE = 'normal'

    @staticmethod
    async def get_api_key(id: UUID4) -> Row[Any]:
        """Get a API Key from the legacy database.

        Args:
            id (UUID4): id of the API Key

        Returns:
            Row: api_keys table row
        """
        async with get_read_session_with_context() as session:
            legacy_api_keys = metadata_legacy.tables['api_keys']
            stmt = select(legacy_api_keys).where(legacy_api_keys.c.id == id)
            return (await session.execute(stmt)).one()

    @staticmethod
    async def create_api_key(
        id: UUID4,
        name: str,
        secret: str,
        service_id: UUID4,
        key_type: str,
        revoked: bool,
        created_at: datetime,
        created_by_id: UUID4,
        version: int,
    ) -> Row[Any]:
        """Create a API Key for the legacy database.

        Args:
            id (UUID4): id of this API Key
            name (str): API Key name
            secret (str): The secret value
            service_id (UUID4): Associated Service id (FK)
            key_type (str): The key type
            revoked (bool): Is key revoked
            created_at (datetime): Time of creation
            created_by_id (UUID4): User that created this API Key
            version (int): Version of this API Key

        Returns:
            Row[Any]: Object representing a API Key
        """
        async with get_write_session_with_context() as session:
            legacy_api_keys = metadata_legacy.tables['api_keys']
            insert_stmt = insert(legacy_api_keys).values(
                id=id,
                name=name,
                secret=secret,
                service_id=service_id,
                key_type=key_type,
                revoked=revoked,
                created_at=created_at,
                created_by_id=created_by_id,
                version=version,
            )
            try:
                await session.execute(insert_stmt)
                await session.commit()
            except Exception:
                raise
            select_stmt = select(legacy_api_keys).where(legacy_api_keys.c.id == id)
            return (await session.execute(select_stmt)).one()
