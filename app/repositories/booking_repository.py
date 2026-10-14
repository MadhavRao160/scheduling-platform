"""Booking queries. No commits, no decisions."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.models.booking import Booking
from app.models.slot import Slot


async def add(session: AsyncSession, booking: Booking) -> Booking:
    """Insert and flush, so the generated id is available before commit."""
    session.add(booking)
    await session.flush()
    await session.refresh(booking)
    return booking


async def list_for_host(
    session: AsyncSession,
    host_id: int,
    status: str | None,
    start: datetime | None,
    end: datetime | None,
) -> Sequence[Booking]:
    """The host's bookings with slot and event type, in ONE query (no N+1).

    The slot is JOINed because we filter and sort on its startAt;
    contains_eager tells SQLAlchemy to fill `booking.slot` from that same
    join instead of issuing another query. The event type comes in through
    joinedload, which adds a second JOIN to the same SELECT.
    """
    stmt = (
        select(Booking)
        .join(Booking.slot)
        .options(contains_eager(Booking.slot), joinedload(Booking.event_type))
        .where(Booking.host_id == host_id)
        .order_by(Slot.start_at, Booking.id)
    )
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    if start is not None:
        stmt = stmt.where(Slot.start_at >= start)
    if end is not None:
        stmt = stmt.where(Slot.start_at <= end)
    return (await session.execute(stmt)).scalars().all()
