"""The data access objects for Services."""

from datetime import datetime
from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, insert, select

from app.db.db_init import get_read_session_with_context, get_write_session_with_context, metadata_legacy


class LegacyUserDao:
    """A class to handle the data access for users in the legacy database.

    Methods:
        get_user: Get a User from the legacy database.
    """

    @staticmethod
    async def get_user(id: UUID4) -> Row[Any]:
        """Get a User from the legacy database.

        Args:
            id (UUID4): id of the User

        Returns:
            Row: users table row
        """
        async with get_read_session_with_context() as session:
            legacy_users = metadata_legacy.tables['users']
            stmt = select(legacy_users).where(legacy_users.c.id == id)
            return (await session.execute(stmt)).first()

    @staticmethod
    async def create_user(
        id: UUID4,
        name: str,
        email_address: str,
        created_at: datetime,
        failed_login_count: int,
        state: str,
        platform_admin: bool,
        blocked: bool,
    ) -> Row[Any]:
        """Create a User for the legacy database.

        Returns:
            Row: created users table row
        """
        async with get_write_session_with_context() as session:
            legacy_users = metadata_legacy.tables['users']
            stmt = insert(legacy_users).values(
                id=id,
                name=name,
                email_address=email_address,
                created_at=created_at,
                failed_login_count=failed_login_count,
                state=state,
                platform_admin=platform_admin,
                blocked=blocked,
            )
            try:
                await session.execute(stmt)
                await session.commit()
            except Exception:
                # log
                raise
            stmt = select(legacy_users).where(legacy_users.c.id == id)
            return (await session.execute(stmt)).first()
