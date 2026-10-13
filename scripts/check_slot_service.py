"""End-to-end check of regenerate_host_slots against the real database.

Creates a throwaway host, runs the scenarios, prints results, then deletes
the host (ON DELETE CASCADE removes its event type, rule, exception, slots).
Run: uv run python -m scripts.check_slot_service
"""

import asyncio
import datetime as dt
from datetime import UTC, datetime

from sqlalchemy import delete, select, text, update
from ulid import ULID

from app.database import engine, session_factory
from app.models import AvailabilityException, AvailabilityRule, EventType, Slot, User
from app.services.slot_service import regenerate_host_slots

NOW = datetime(2026, 10, 19, 0, 0, tzinfo=UTC)  # fixed "now" so results never drift
RANGE = {"from_date": dt.date(2026, 10, 19), "to_date": dt.date(2026, 10, 26), "now": NOW}


async def slots(host_id: int) -> list[str]:
    async with session_factory() as s:
        rows = (
            await s.execute(
                select(Slot.start_at, Slot.status).where(Slot.host_id == host_id).order_by(Slot.start_at)
            )
        ).all()
    return [f"{r.start_at:%m-%d %H:%M} {r.status}" for r in rows]


def check(label: str, got: object, expected: object) -> None:
    print(f"{'PASS' if got == expected else 'FAIL'}  {label}")
    if got != expected:
        print(f"      got:      {got}\n      expected: {expected}")


async def main() -> None:
    tag = str(ULID()).lower()
    async with session_factory() as s:
        host = User(email=f"check-{tag}@example.com", name="Slot Check", slug=f"check-{tag}", timezone="Europe/London")
        s.add(host)
        await s.flush()
        s.add(EventType(host_id=host.id, title="Check", slug="check", duration_minutes=30,
                        buffer_before_minutes=10, buffer_after_minutes=5))
        # Mondays 09:00-12:00 London. 19 Oct is BST (UTC+1), 26 Oct is GMT (UTC+0).
        s.add(AvailabilityRule(user_id=host.id, weekday=1, start_time="09:00", end_time="12:00",
                               timezone="Europe/London"))
        await s.commit()
    host_id = host.id

    try:
        await regenerate_host_slots(host_id, **RANGE)
        first = await slots(host_id)
        check("DST: 19th starts 08:10 UTC, 26th starts 09:10 UTC", first, [
            "10-19 08:10 AVAILABLE", "10-19 08:40 AVAILABLE", "10-19 09:10 AVAILABLE",
            "10-19 09:40 AVAILABLE", "10-19 10:10 AVAILABLE",
            "10-26 09:10 AVAILABLE", "10-26 09:40 AVAILABLE", "10-26 10:10 AVAILABLE",
            "10-26 10:40 AVAILABLE", "10-26 11:10 AVAILABLE",
        ])

        await regenerate_host_slots(host_id, **RANGE)
        check("idempotent: second run changes nothing", await slots(host_id), first)

        async with session_factory() as s:
            await s.execute(text(
                "UPDATE slots SET status = 'BOOKED' WHERE \"hostId\" = :h AND \"startAt\" = '2026-10-26 09:40'"
            ), {"h": host_id})
            await s.commit()
        await regenerate_host_slots(host_id, **RANGE)
        after_booking = await slots(host_id)
        check("booking 09:40 blocks both neighbours, stays BOOKED", after_booking[5:], [
            "10-26 09:10 BLOCKED", "10-26 09:40 BOOKED", "10-26 10:10 BLOCKED",
            "10-26 10:40 AVAILABLE", "10-26 11:10 AVAILABLE",
        ])

        async with session_factory() as s:
            s.add(AvailabilityException(user_id=host_id, date=dt.date(2026, 10, 19), type="BLOCK_FULL_DAY",
                                        timezone="Europe/London"))
            await s.commit()
        await regenerate_host_slots(host_id, **RANGE)
        check("full-day block on 19th", (await slots(host_id))[:5], ["10-19 08:10 BLOCKED", "10-19 08:40 BLOCKED",
              "10-19 09:10 BLOCKED", "10-19 09:40 BLOCKED", "10-19 10:10 BLOCKED"])

        async with session_factory() as s:
            await s.execute(update(EventType).where(EventType.host_id == host_id).values(is_active=False))
            await s.commit()
        await regenerate_host_slots(host_id, **RANGE)
        statuses = {line.split()[-1] for line in await slots(host_id)}
        check("deactivated event type: only BOOKED and BLOCKED remain", statuses, {"BOOKED", "BLOCKED"})
    finally:
        async with session_factory() as s:
            await s.execute(delete(User).where(User.id == host_id))
            await s.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())