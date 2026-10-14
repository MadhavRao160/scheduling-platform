"""Bookings (Part 2, Section 10).

Two concurrency strategies, both correct under any number of simultaneous
requests for the same slot (Section 10.5):

- create_booking             PESSIMISTIC: lock the row, check, update.  ROUTED.
- create_booking_optimistic  OPTIMISTIC: one conditional UPDATE.        NOT ROUTED.

Both commit before starting any workflow, and no workflow start can fail the
request (Sections 7.1 rule 4 and 7.4).
"""

from datetime import UTC, datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, not_found
from app.models.booking import Booking, BookingStatus
from app.models.slot import Slot, SlotStatus
from app.repositories import booking_repository, slot_repository
from app.schemas.booking import (
    BookingCreate,
    BookingCreated,
    BookingCreateResponse,
    BookingEventTypeSummary,
    BookingListItem,
    BookingListQuery,
    BookingListResponse,
)
from app.temporal.client import start_regenerate_host_slots
from app.utils.utc import from_db, to_db

END_OF_DAY = time(23, 59, 59, 999000)


# ---------------------------------------------------------------------- list


async def list_bookings(
    session: AsyncSession, host_id: int, query: BookingListQuery
) -> BookingListResponse:
    start = datetime.combine(query.from_, time.min) if query.from_ else None  # naive UTC
    end = datetime.combine(query.to, END_OF_DAY) if query.to else None
    bookings = await booking_repository.list_for_host(
        session, host_id, query.status, start, end
    )
    return BookingListResponse(
        bookings=[
            BookingListItem(
                id=b.id,
                status=b.status,
                invitee_email=b.invitee_email,
                invitee_name=b.invitee_name,
                invitee_notes=b.invitee_notes,
                start_at=b.slot.start_at,
                end_at=b.slot.end_at,
                event_type=BookingEventTypeSummary.model_validate(b.event_type),
            )
            for b in bookings
        ]
    )


# -------------------------------------------------------------------- shared


def _check_bookable(slot: Slot | None, host_id: int, now: datetime) -> Slot:
    """The three rule checks from Section 10.2, in the spec's order."""
    if slot is None or slot.host_id != host_id:
        raise not_found("Slot")  # another host's slot looks exactly like a missing one
    if slot.status != SlotStatus.AVAILABLE:
        raise BadRequestError("Slot is not available")
    if from_db(slot.start_at) <= now:
        raise BadRequestError("Slot has already started")
    return slot


def _new_booking(host_id: int, event_type_id: int, slot_id: str, payload: BookingCreate) -> Booking:
    return Booking(
        host_id=host_id,
        event_type_id=event_type_id,
        slot_id=slot_id,
        invitee_email=str(payload.invitee_email),
        invitee_name=payload.invitee_name,
        invitee_notes=payload.invitee_notes,
        status=BookingStatus.CONFIRMED,
    )


async def _after_commit(host_id: int, start_at: datetime) -> None:
    """Fire-and-forget side effects. Runs only after a successful commit.

    The booked date is narrowed in UTC; regenerate_host_slots widens it by a
    day on each side internally, so neighbours across local midnight are covered.
    Email and calendar starters are added in Steps 8 and 9.
    """
    booked_day = start_at.date()
    await start_regenerate_host_slots(host_id, booked_day, booked_day)


def _response(booking: Booking, start_at: datetime, end_at: datetime) -> BookingCreateResponse:
    return BookingCreateResponse(
        booking=BookingCreated(id=booking.id, status=booking.status, start_at=start_at, end_at=end_at)
    )


# ------------------------------------------------------- pessimistic (routed)


async def create_booking(
    session: AsyncSession, host_id: int, payload: BookingCreate, *, now: datetime | None = None
) -> BookingCreateResponse:
    now = now or datetime.now(UTC)

    # 1. SELECT ... FOR UPDATE. From here until commit/rollback, this
    #    transaction owns the row. A competing request for the same slot
    #    blocks on this line until we finish.
    slot = await slot_repository.get_for_update(session, payload.slot_id)

    # 2. Check while holding the lock. Nobody can change the row between this
    #    check and our update. A loser that waited sees status = BOOKED here.
    #    Raising leaves the transaction to get_session, which rolls back and
    #    so releases the lock.
    slot = _check_bookable(slot, host_id, now)

    # 3. Write both rows inside the same transaction.
    slot.status = SlotStatus.BOOKED
    booking = await booking_repository.add(
        session, _new_booking(host_id, slot.event_type_id, slot.id, payload)
    )

    # 4. COMMIT releases the lock. Waiting requests wake up now.
    await session.commit()

    # 5. Only now: network calls (Temporal). Never inside the transaction.
    await _after_commit(host_id, slot.start_at)
    return _response(booking, slot.start_at, slot.end_at)


# --------------------------------------------------- optimistic (not routed)


async def create_booking_optimistic(
    session: AsyncSession, host_id: int, payload: BookingCreate, *, now: datetime | None = None
) -> BookingCreateResponse:
    now = now or datetime.now(UTC)

    # 1. One atomic conditional UPDATE. Whoever's UPDATE reaches the row first
    #    flips it to BOOKED. A concurrent UPDATE on the same row waits for that
    #    transaction, then re-checks its WHERE against the committed row,
    #    finds status = 'BOOKED', and matches 0 rows.
    claimed = await slot_repository.claim_if_available(session, payload.slot_id, host_id, to_db(now))

    if claimed is None:
        # 2a. 0 rows. Read once to report the precise reason: missing or
        #     another host's (404), started (400), or taken (400).
        _check_bookable(await slot_repository.get_by_id(session, payload.slot_id), host_id, now)
        raise BadRequestError("Slot is not available")  # it changed between our UPDATE and read

    # 2b. 1 row: the slot is ours. Insert the booking in the same transaction.
    booking = await booking_repository.add(
        session, _new_booking(host_id, claimed.event_type_id, claimed.id, payload)
    )
    await session.commit()

    await _after_commit(host_id, claimed.start_at)
    return _response(booking, claimed.start_at, claimed.end_at)
