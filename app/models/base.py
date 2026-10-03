"""Shared foundations for every SQLAlchemy model.

`Base` is the registry SQLAlchemy requires: declaring a class that inherits it
records the table in metadata, which is also what Alembic diffs against when
generating migrations.

`TimestampMixin` carries the two columns every table in the schema has. It is
not a table itself — only a source of columns for the classes that inherit it.
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base. Every model inherits this."""


class TimestampMixin:
    """The createdAt / updatedAt pair carried by every table.

    Both are TIMESTAMP(3) without time zone: UTC is a convention the
    application enforces rather than something the column records.

    createdAt is filled by the database on insert; updatedAt is maintained by
    the application through `onupdate`, which SQLAlchemy applies on every
    UPDATE it issues for the row.
    """

    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        TIMESTAMP(timezone=False, precision=3),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt",
        TIMESTAMP(timezone=False, precision=3),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.now(),
    )