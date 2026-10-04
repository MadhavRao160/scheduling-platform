"""The `availability_rules` table — recurring weekly availability.

A row means "on this weekday, from startTime to endTime, local time in this
timezone". Times are stored as HH:mm text alongside the zone name, not as UTC,
because the same local time is a different UTC moment in summer and winter.

weekday uses 0 = Sunday … 6 = Saturday.
"""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AvailabilityRule(Base, TimestampMixin):
    __tablename__ = "availability_rules"
    __table_args__ = (
        Index("ix_availability_rules_user_weekday", "userId", "weekday"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        "userId",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column("startTime", Text, nullable=False)
    end_time: Mapped[str] = mapped_column("endTime", Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        "isActive", Boolean, nullable=False, server_default="true"
    )
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")