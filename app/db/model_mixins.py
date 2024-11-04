"""Database mixin models for the application.

https://docs.sqlalchemy.org/en/20/orm/declarative_mixins.html#mixing-in-columns
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP


class TimestampMixin:
    """A mix-in class to add some timestamp columns.

    In the database, the columns should have the Postgres type "timestamp with time zone".

    https://www.postgresql.org/docs/16/datatype-datetime.html
    """

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=func.now())
