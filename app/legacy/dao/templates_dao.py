"""The data access objects for templates."""

from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, select

from app.db.db_init import get_read_session_with_context, metadata_legacy


class LegacyTemplateDao:
    """A class to handle the data access for templates in the legacy database.

    Methods:
        get_template: Get a Template from the legacy database.
    """

    @staticmethod
    async def get_template(id: UUID4) -> Row[Any]:
        """Get a Template from the legacy database.

        Args:
            id (UUID4): id of the template

        Returns:
            Row: template table row
        """
        async with get_read_session_with_context(enp=False) as session:
            legacy_templates = metadata_legacy.tables['templates']
            stmt = select(legacy_templates).where(legacy_templates.c.id == id)
            return (await session.execute(stmt)).one()
