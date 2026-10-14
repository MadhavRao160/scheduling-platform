"""Section 10.5 correctness bar, against the real database, for BOTH strategies.

For each strategy: N simultaneous bookings of the same slot, each in its own
session (like N separate HTTP requests). Then checks:
  exactly one success, every other gets 400 "Slot is not available",
  exactly one bookings row for the slot, and the slot ends BOOKED.

Creates a throwaway host and deletes it at the end (cascade removes the rest).
Temporal is switched off for this run, so no workflows are started.
Run: uv run python -m scripts.check_booking_concurrency
"""

import asyncio
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from ulid import ULID

from app.config.settings import settings
from app.database import engine, session_factory
from app.errors import ApiError
from app.models import Booking, EventType, Slot, User
from app.schemas.booking import BookingCreate
from app.services import booking_service
from app.utils.utc import to_db

N = 25  # more than the default connection pool (5 + 10 overflow), on purpose


async def attempt(strategy, host_id: int, slot_id: str, i: int) -> str:
    """One 'request': own session; commit or roll back exactly once."""
    payload = BookingCreate(slot_id=slot_id, invitee_email=f"guest{i}@example.com", invitee_name=f"Guest {i}")
    async with session_factory() as session:
        try:
            await strategy(session, host_id, payload)
            return "201"
        except ApiError as e:
            await session.rollback()
            return f"{e.status_code} {e.message}"
        except Exception as e:  # anything else is a bug: show it
            await session.rollback()
            return f"UNEXPECTED {type(e).__name__}: {e}"


async def run(label: str, strategy, host_id: int, event_type_id: int) -> bool:
    start = datetime.now(UTC) + timedelta(days=2)
    slot = Slot(host_id=host_id, event_type_id=event_type_id, start_at=to_db(start),
                end_at=to_db(start + timedelta(minutes=30)))
    async with session_factory() as s:
        s.add(slot)
        await s.commit()

    began = time.perf_counter()
    results = await asyncio.gather(*(attempt(strategy, host_id, slot.id, i) for i in range(N)))
    elapsed = time.perf_counter() - began

    async with session_factory() as s:
        rows = await s.scalar(select(func.count()).select_from(Booking).where(Booking.slot_id == slot.id))
        status = await s.scalar(select(Slot.status).where(Slot.id == slot.id))

    counts = Counter(results)
    ok = (
        counts.get("201") == 1
        and counts.get("400 Slot is not available") == N - 1
        and rows == 1
        and status == "BOOKED"
    )
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {dict(counts)} | booking rows={rows} | slot={status} | {elapsed:.2f}s")
    return ok


async def main() -> None:
    settings.temporal_enabled = False
    tag = str(ULID()).lower()
    async with session_factory() as s:
        host = User(email=f"race-{tag}@example.com", name="Race Check", slug=f"race-{tag}", timezone="UTC")
        s.add(host)
        await s.flush()
        event_type = EventType(host_id=host.id, title="Race", slug="race", duration_minutes=30)
        s.add(event_type)
        await s.commit()

    try:
        await run("pessimistic (SELECT ... FOR UPDATE)", booking_service.create_booking, host.id, event_type.id)
        await run("optimistic  (conditional UPDATE)   ", booking_service.create_booking_optimistic, host.id, event_type.id)
    finally:
        async with session_factory() as s:
            await s.execute(delete(User).where(User.id == host.id))
            await s.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
