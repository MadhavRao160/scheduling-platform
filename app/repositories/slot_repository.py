"""Slot queries. Builds SQL only: no commits, no decisions, no raised errors.

All datetimes passed in and returned are naive UTC (the database convention).
Convert with app.utils.utc at the service boundary.

Every write carries `status <> 'BOOKED'`, so a booked slot is never changed
here even if the calling code has a bug (Section 8.4, defence in depth).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Row, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_type import EventType
from app.models.slot import Slot, SlotStatus

# PostgreSQL allows at most 32,767 bind parameters per statement.
# Upsert rows carry 6 values each, so 1,000 rows stays far below the limit.
CHUNK_SIZE = 1000


def _chunks(items: Sequence[Any], size: int = CHUNK_SIZE):
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def upsert_available(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> None:
    """Insert new slots as AVAILABLE; re-open existing non-booked ones.

    Each row: id, host_id, event_type_id, start_at, end_at (naive UTC).
    On conflict only status and updatedAt change, so an existing slot keeps
    its id across regenerations.
    """
    for chunk in _chunks(rows):
        values = [{**row, "status": SlotStatus.AVAILABLE} for row in chunk]
        stmt = insert(Slot).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_slots_event_type_start_end",
            set_={Slot.status: SlotStatus.AVAILABLE, Slot.updated_at: func.now()},
            where=Slot.status != SlotStatus.BOOKED,
        )
        await session.execute(stmt)


async def find_booked_by_host_in_range(
    session: AsyncSession, host_id: int, range_start: datetime, range_end: datetime
) -> Sequence[Row[tuple[datetime, datetime]]]:
    """(start_at, end_at) of the host's BOOKED slots overlapping the range.

    Host-wide, across every event type: a booked 30-minute meeting also
    blocks the host's 60-minute event type at that time.
    """
    stmt = (
        select(Slot.start_at, Slot.end_at)
        .where(
            Slot.host_id == host_id,
            Slot.status == SlotStatus.BOOKED,
            Slot.start_at < range_end,
            Slot.end_at > range_start,
        )
        .order_by(Slot.start_at)
    )
    return (await session.execute(stmt)).all()


async def find_reconcilable(
    session: AsyncSession,
    event_type_id: int,
    range_start: datetime,
    range_end: datetime,
    now: datetime,
) -> Sequence[Row[tuple[str, datetime, datetime]]]:
    """(id, start_at, end_at) of future AVAILABLE/BLOCKED slots in range.

    BOOKED slots are never selected, so they can never be reconciled.
    """
    stmt = select(Slot.id, Slot.start_at, Slot.end_at).where(
        Slot.event_type_id == event_type_id,
        Slot.status.in_([SlotStatus.AVAILABLE, SlotStatus.BLOCKED]),
        Slot.start_at > now,
        Slot.start_at >= range_start,
        Slot.start_at <= range_end,
    )
    return (await session.execute(stmt)).all()


async def mark_blocked(session: AsyncSession, slot_ids: Sequence[str]) -> None:
    """Set the given slots to BLOCKED, skipping any that are BOOKED."""
    for chunk in _chunks(slot_ids):
        stmt = (
            update(Slot)
            .where(Slot.id.in_(chunk), Slot.status != SlotStatus.BOOKED)
            .values(status=SlotStatus.BLOCKED, updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await session.execute(stmt)


async def block_available_for_inactive_event_types(
    session: AsyncSession, host_id: int, now: datetime
) -> None:
    """Future AVAILABLE slots of the host's inactive event types -> BLOCKED."""
    inactive_ids = select(EventType.id).where(
        EventType.host_id == host_id, EventType.is_active.is_(False)
    )
    stmt = (
        update(Slot)
        .where(
            Slot.host_id == host_id,
            Slot.event_type_id.in_(inactive_ids),
            Slot.status == SlotStatus.AVAILABLE,
            Slot.start_at > now,
        )
        .values(status=SlotStatus.BLOCKED, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    await session.execute(stmt)

async def find_available_for_event_type(
    session: AsyncSession,
    event_type_id: int,
    range_start: datetime,
    range_end: datetime,
    now: datetime,
) -> Sequence[Slot]:
    """Bookable slots starting in [range_start, range_end), soonest first.

    Matches the index (eventTypeId, startAt, status).
    """
    stmt = (
        select(Slot)
        .where(
            Slot.event_type_id == event_type_id,
            Slot.status == SlotStatus.AVAILABLE,
            Slot.start_at > now,
            Slot.start_at >= range_start,
            Slot.start_at < range_end,
        )
        .order_by(Slot.start_at)
    )
    return (await session.execute(stmt)).scalars().all()

# ------------------------------------------------------------ booking writes


async def get_for_update(session: AsyncSession, slot_id: str) -> Slot | None:
    """PESSIMISTIC lock: SELECT ... FROM slots WHERE id = :id FOR UPDATE.

    The row lock is held until this transaction commits or rolls back. Any
    other transaction asking for the same row FOR UPDATE waits here.
    populate_existing makes SQLAlchemy overwrite any copy of the row already
    in the session, so we read the values as of the moment we got the lock.
    """
    stmt = (
        select(Slot)
        .where(Slot.id == slot_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_id(session: AsyncSession, slot_id: str) -> Slot | None:
    return await session.get(Slot, slot_id)


async def claim_if_available(
    session: AsyncSession, slot_id: str, host_id: int, now: datetime
) -> Row[tuple[str, int, datetime, datetime]] | None:
    """OPTIMISTIC claim: one conditional UPDATE, no explicit lock.

    UPDATE slots SET status = 'BOOKED'
    WHERE id = :id AND "hostId" = :host AND status = 'AVAILABLE' AND "startAt" > :now
    RETURNING id, "eventTypeId", "startAt", "endAt"

    Returns the claimed slot's values, or None when no row matched (someone
    else won, or the slot was never bookable).
    """
    stmt = (
        update(Slot)
        .where(
            Slot.id == slot_id,
            Slot.host_id == host_id,
            Slot.status == SlotStatus.AVAILABLE,
            Slot.start_at > now,
        )
        .values(status=SlotStatus.BOOKED, updated_at=func.now())
        .returning(Slot.id, Slot.event_type_id, Slot.start_at, Slot.end_at)
        .execution_options(synchronize_session=False)
    )
    return (await session.execute(stmt)).one_or_none()
