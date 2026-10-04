"""The `availability_exceptions` table — per-date overrides on the weekly rules.

Three kinds:
- BLOCK_FULL_DAY       unavailable all day; no times
- BLOCK_PARTIAL        remove startTime–endTime from that day
- ADD_AVAILABLE_WINDOW add startTime–endTime on that day

startTime and endTime are nullable because BLOCK_FULL_DAY has none. Which
combinations are valid is enforced in the schema layer, not here.
"""

import datetime
from sqlalchemy import Date, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin

class AvailabilityException(Base, TimestampMixin):
    __tablename__ = "availability_exceptions"
    __table_args__ = (
        Index("ix_availability_exceptions_user_date", "userId", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        "userId",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)

    start_time: Mapped[str | None] = mapped_column("startTime", Text, nullable=True)
    end_time: Mapped[str | None] = mapped_column("endTime", Text, nullable=True)

    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)