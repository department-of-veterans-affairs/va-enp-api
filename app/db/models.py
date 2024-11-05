"""Database models for the application."""

from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

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

    def get_template_by_id(session: Session, template_id: UUID) -> 'Template':
        """Retrieve a template by its ID from the database.

        Args:
        ----
            session (Session): The database session to use for the query.
            template_id (UUID): The ID of the template to retrieve.

        Returns:
        -------
            Template: The retrieved template object, or None if not found.

        """
        return session.get(Template, template_id)

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
