"""The `event_types` table.

A bookable product a host publishes — "30 Minute Intro Call". Owned by one
host; deleting the host deletes their event types.

The buffer columns describe padding around a meeting. Nothing in Part 1 reads
them; they are stored and validated now because later scheduling depends on them.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from app.models.base import Base, TimestampMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship


class EventType(Base, TimestampMixin):
    __tablename__ = "event_types"
    __table_args__ = (
        # Two hosts may each own "30-minute-meeting"; one host may not own it twice.
        UniqueConstraint("hostId", "slug", name="uq_event_types_host_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    host_id: Mapped[int] = mapped_column(
        "hostId",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False)

    duration_minutes: Mapped[int] = mapped_column("durationMinutes", Integer, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        "isActive", Boolean, nullable=False, server_default="true"
    )

    location_type: Mapped[str] = mapped_column(
        "locationType", Text, nullable=False, server_default="online"
    )
    location_value: Mapped[str | None] = mapped_column("locationValue", Text, nullable=True)

    buffer_before_minutes: Mapped[int] = mapped_column(
        "bufferBeforeMinutes", Integer, nullable=False, server_default="0"
    )
    buffer_after_minutes: Mapped[int] = mapped_column(
        "bufferAfterMinutes", Integer, nullable=False, server_default="0"
    )
    host: Mapped["User"] = relationship(lazy="raise")