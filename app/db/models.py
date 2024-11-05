"""Database models for the application."""

from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_mixins import TimestampMixin


class Notification(TimestampMixin, Base):
    """Database table for notifications."""

    __tablename__ = 'notifications'

    id: Mapped[UUID[str]] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    personalization: Mapped[str] = mapped_column(String, nullable=True)


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

    def build_message(self, personalization: dict[str, str]) -> str:
        """Return the template body populated with the personalized values.

        Args:
        ----
            personalization: A dictionary of template placeholder names and their values

        Returns:
        -------
            str: The template body populated with the personalized values

        """
        # This method supports #26.  When this class contains more columns, including the template
        # body, finish this implementation, and remove any associated mocking in the tests for #26.
        raise NotImplementedError
