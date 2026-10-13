from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ulid import ULID

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.event_type import EventType


class SlotStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"


def new_slot_id() -> str:
    """Time-sortable, collision-resistant id, made in Python (no DB round trip)."""
    return str(ULID())


class Slot(Base, TimestampMixin):
    __tablename__ = "slots"
    __table_args__ = (
        # Idempotency key for slot generation; the upsert targets it by name.
        UniqueConstraint("eventTypeId", "startAt", "endAt", name="uq_slots_event_type_start_end"),
        CheckConstraint("status IN ('AVAILABLE', 'BOOKED', 'BLOCKED')", name="ck_slots_status"),
        Index("ix_slots_host_start", "hostId", "startAt"),
        Index("ix_slots_event_type_start_status", "eventTypeId", "startAt", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_slot_id)
    host_id: Mapped[int] = mapped_column(
        "hostId", ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type_id: Mapped[int] = mapped_column(
        "eventTypeId", ForeignKey("event_types.id", ondelete="CASCADE"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(
        "startAt", TIMESTAMP(timezone=False, precision=3), nullable=False
    )  # UTC, stored naive
    end_at: Mapped[datetime] = mapped_column(
        "endAt", TIMESTAMP(timezone=False, precision=3), nullable=False
    )  # UTC, stored naive
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=SlotStatus.AVAILABLE, server_default=text("'AVAILABLE'")
    )

    event_type: Mapped["EventType"] = relationship(lazy="raise")