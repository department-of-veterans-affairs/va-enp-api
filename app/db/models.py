"""Database models for the application."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_mixins import TimestampMixin

Base = declarative_base()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(TimestampMixin, Base):
    """Database table for notifications."""

    __tablename__ = 'notifications'

    # Define table arguments properly for partitioning
    __table_args__ = {
        'postgresql_partition_by': 'RANGE (created_at)',
    }

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    personalization: Mapped[str | None] = mapped_column(String, nullable=True)


def create_year_partition(target, connection, **kw):
    """Creates partition for the current year"""
    year = datetime.utcnow().year

    # Create partition for current year
    connection.execute(f"""
    CREATE TABLE IF NOT EXISTS notifications_{year}
    PARTITION OF notifications
    FOR VALUES FROM ('{year}-01-01 00:00:00') 
    TO ('{year+1}-01-01 00:00:00');
    
    -- Create index on created_at for the partition
    CREATE INDEX IF NOT EXISTS idx_notifications_{year}_created_at 
    ON notifications_{year} (created_at);
    """)


# Register event listener for partition creation
event.listen(Notification.__table__, 'after_create', create_year_partition)


# Function to ensure future partitions exist
def ensure_future_partition(connection, date: datetime):
    """Ensures partition exists for the given date"""
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
