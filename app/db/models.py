"""Database models for the application."""

from datetime import datetime
from typing import ClassVar
from uuid import uuid4

from loguru import logger
from sqlalchemy import MetaData, String, event, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_mixins import TimestampMixin

metadata = MetaData()

NOTIFICATION_STARTING_PARTITION_YEAR = 2024


class Notification(TimestampMixin, Base):
    """Database table for notifications."""

    __tablename__ = 'notifications'

    __table_args__: ClassVar = {'postgresql_partition_by': 'RANGE (created_at)'}

    __mapper_args__: ClassVar = {'primary_key': ['id', 'created_at']}

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid4)
    personalization: Mapped[str | None] = mapped_column(String, nullable=True)


def create_notification_year_partition(target: Base, connection: Connection, **kw: any) -> None:
    """Creates year-based partitions for all years from the start year to the next year.

    Args:
        target (Base): The target table to create partitions for.
        connection (Connection): The database connection used to execute SQL statements.
        **kw (any): Additional keyword arguments passed by SQLAlchemy.

    Raises:
        SQLAlchemyError: If an error occurs while creating a partition.
    """
    current_year = datetime.utcnow().year

    for year in range(NOTIFICATION_STARTING_PARTITION_YEAR, current_year + 2):
        try:
            sql = text(f"""
                CREATE TABLE IF NOT EXISTS notifications_{year}
                PARTITION OF notifications
                FOR VALUES FROM ('{year}-01-01')
                TO ('{year + 1}-01-01');

                CREATE INDEX IF NOT EXISTS idx_notifications_{year}_created_at
                ON notifications_{year} (created_at);
            """)

            connection.execute(sql)

            logger.info('Partition for year {} ensured.', {})
        except SQLAlchemyError as e:
            logger.critical('Error creating partition for year {}: {}', year, e)
            raise


# Register event listener for notification year-based partition creation
event.listen(Notification.__table__, 'after_create', create_notification_year_partition)


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
