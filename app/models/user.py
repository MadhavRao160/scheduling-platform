"""The `users` table.

A host. Everything else in the schema hangs off this row: event types,
availability rules and exceptions all reference it with ON DELETE CASCADE.

Storage only — no business rules live here. Slug derivation, duplicate-email
checks and the like belong in the service.
"""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)

    # Unique globally, unlike event-type slugs which are unique per host.
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # An IANA identifier such as "Asia/Kolkata". Validated at the schema layer
    # against zoneinfo, so an unresolvable zone never reaches this column.
    timezone: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="UTC"
    )