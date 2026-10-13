from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.event_type import EventType
    from app.models.slot import Slot
    from app.models.user import User


class BookingStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        # Last line of defence for "exactly one booking per slot" (Section 10.5).
        # A UNIQUE constraint also creates an index, so no separate slotId index.
        UniqueConstraint("slotId", name="uq_bookings_slot"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED')", name="ck_bookings_status"
        ),
        Index("ix_bookings_status", "status"),
        Index("ix_bookings_invitee_email", "inviteeEmail"),
        Index("ix_bookings_host_created", "hostId", "createdAt"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)  # SERIAL
    host_id: Mapped[int] = mapped_column(
        "hostId", ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type_id: Mapped[int] = mapped_column(
        "eventTypeId", ForeignKey("event_types.id", ondelete="CASCADE"), nullable=False
    )
    slot_id: Mapped[str] = mapped_column(
        "slotId", Text, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False
    )
    invitee_email: Mapped[str] = mapped_column("inviteeEmail", Text, nullable=False)
    invitee_name: Mapped[str] = mapped_column("inviteeName", Text, nullable=False)
    invitee_notes: Mapped[str | None] = mapped_column("inviteeNotes", Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=BookingStatus.PENDING, server_default=text("'PENDING'")
    )
    meet_link: Mapped[str | None] = mapped_column("meetLink", Text)               # filled later
    calendar_event_id: Mapped[str | None] = mapped_column("calendarEventId", Text)  # filled later
    cancelled_at: Mapped[datetime | None] = mapped_column(
        "cancelledAt", TIMESTAMP(timezone=False, precision=3)
    )

    host: Mapped["User"] = relationship(lazy="raise")
    event_type: Mapped["EventType"] = relationship(lazy="raise")
    slot: Mapped["Slot"] = relationship(lazy="raise")