"""Database models for the application."""

from datetime import datetime
from typing import ClassVar
from uuid import uuid4

from sqlalchemy import String, event, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_mixins import TimestampMixin


class Notification(TimestampMixin, Base):
    """Database table for notifications."""

    __tablename__ = 'notifications'

    __table_args__: ClassVar = ({'postgresql_partition_by': 'RANGE (created_at)'},)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid4)
    personalization: Mapped[str | None] = mapped_column(String, nullable=True)

    __mapper_args__: ClassVar = {'primary_key': ['id', 'created_at']}


def create_year_partition(target: Base, connection: any, **kw: any) -> None:
    """Creates partition for the current year."""
    year = datetime.utcnow().year

    # Create partition for the current year
    sql = text(f"""
    CREATE TABLE IF NOT EXISTS notifications_{year}
    PARTITION OF notifications
    FOR VALUES FROM ('{year}-01-01 00:00:00')
    TO ('{year+1}-01-01 00:00:00');

    CREATE INDEX IF NOT EXISTS idx_notifications_{year}_created_at
    ON notifications_{year} (created_at);
    """)

    # Execute the SQL using SQLAlchemy's text()
    connection.execute(sql)


# Register event listener for partition creation
event.listen(Notification.__table__, 'after_create', create_year_partition)


def ensure_future_partition(connection: any, date: datetime) -> None:
    """Ensures partition exists for the given date."""
    year = date.year
    partition_name = f'notifications_{year}'

    # Check if partition exists
    exists = connection.execute(f"""
    SELECT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = '{partition_name}'
    );
    """).scalar()

    if not exists:
        connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF notifications
        FOR VALUES FROM ('{year}-01-01 00:00:00')
        TO ('{year+1}-01-01 00:00:00');

        CREATE INDEX IF NOT EXISTS idx_{partition_name}_created_at
        ON {partition_name} (created_at);
        """)


class Service(Base):
    """Database table for VA services (business groups)."""

    __tablename__ = 'services'

    id: Mapped[UUID[str]] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Template(TimestampMixin, Base):
    """Database table for templates."""

    __tablename__ = 'templates'

    id: Mapped[UUID[str]] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))

    def build_message(self, personalization: dict[str, str | int | float] | None) -> str:
        """Return the template body populated with the personalized values.

        Args:
            personalization: A dictionary of template placeholder names and their values

        Returns:
            str: The template body populated with the personalized values

        """
        # This method supports #26.  When this class contains more columns, including the template
        # body, finish this implementation, and remove any associated mocking in the tests for #26.
        raise NotImplementedError
