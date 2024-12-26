"""Database models for the application."""

from uuid import uuid4

from sqlalchemy import String, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.ddl import DDL

from app.db.base import Base
from app.db.model_mixins import TimestampMixin


class NotificationMixin(TimestampMixin):
    id: Mapped[UUID[str]] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    personalization: Mapped[str] = mapped_column(String, nullable=True)

class Notification(NotificationMixin, Base):
    """Database table for notifications."""

    __tablename__ = 'notifications'
    __table_args__ = {
        'postgresql_partition_by': 'RANGE (created_at)'
    }

class Notification2024(NotificationMixin, Base):
    __tablename__ = 'notifications2024'

Notification2024.__table__.add_is_dependent_on(Notification.__table__)

event.listen(
    Notification2024.__table__, 
    'after_create', 
    DDL("""ALTER TABLE notifications ATTACH PARTITION notifications2024 FOR VALUES FROM ('2024-01-01 00:00:00') TO ('2025-01-01 00:00:00');""")
)

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
