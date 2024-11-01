"""Database models for the application."""

from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Test(Base):
    """The 'tests' table."""

    __tablename__ = 'tests'

    id: Mapped[UUID[str]] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    data: Mapped[str] = mapped_column(String(255), nullable=True)
