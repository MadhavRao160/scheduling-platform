"""Slot regeneration: the I/O around the pure slot_generation module (Section 8.3).

Runs inside the Temporal worker, not inside an HTTP request, so it opens its
own sessions from session_factory instead of using get_session.
"""

import asyncio
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any, TypeVar

from app.config.settings import settings
from app.database import session_factory
from app.models.slot import new_slot_id
from app.repositories import (
    availability_exception_repository,
    availability_rule_repository,
    event_type_repository,
    slot_repository,
    user_repository,
)
from app.services import slot_generation as sg
from app.utils.utc import from_db, to_db

logger = logging.getLogger(__name__)

T = TypeVar("T")
END_OF_DAY = time(23, 59, 59, 999000)


async def _read(query: Callable[..., Awaitable[T]], *args: Any) -> T:
    """Run one read in its own session.

    One AsyncSession cannot run two queries at the same time, so each call
    gathered in parallel needs a session of its own (Section 7.5).
    """
    async with session_factory() as session:
        return await query(session, *args)


def resolve_range(
    from_date: dt.date | None, to_date: dt.date | None, now: datetime, horizon_days: int
) -> tuple[datetime, datetime]:
    """Section 8.3 step 2: the UTC range to regenerate."""
    start_day = from_date or now.astimezone(UTC).date()
    end_day = to_date or start_day + timedelta(days=horizon_days)
    return (
        datetime.combine(start_day, time.min, tzinfo=UTC),
        datetime.combine(end_day, END_OF_DAY, tzinfo=UTC),
    )


async def regenerate_host_slots(
    host_id: int,
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    *,
    now: datetime | None = None,
) -> None:
    """Bring the host's materialised slots in line with their availability.

    Idempotent: running it twice leaves identical state. Never reads or
    changes a BOOKED slot. `now` can be passed in for testing.
    """
    now = now or datetime.now(UTC)

    # 1. Host
    host = await _read(user_repository.get_by_id, host_id)
    if host is None:
        return

    # 2. Range. Local dates and UTC dates disagree at the edges, so the date
    #    loop runs one day wider on each side and candidates are then kept
    #    only if they start inside the UTC range (D7).
    range_start, range_end = resolve_range(from_date, to_date, now, settings.slot_generation_days)
    first_day = range_start.date() - timedelta(days=1)
    last_day = range_end.date() + timedelta(days=1)

    # 3. Four independent reads, in parallel, one session each.
    rules, exceptions, event_types, booked_rows = await asyncio.gather(
        _read(availability_rule_repository.find_active_by_user, host_id),
        _read(availability_exception_repository.find_in_date_range, host_id, first_day, last_day),
        _read(event_type_repository.find_active_by_host, host_id),
        _read(
            slot_repository.find_booked_by_host_in_range,
            host_id,
            to_db(range_start - timedelta(days=1)),
            to_db(range_end + timedelta(days=1)),
        ),
    )

    # 4. Plain inputs for the pure functions.
    booked = [sg.TimeWindow(from_db(start), from_db(end)) for start, end in booked_rows]
    rule_inputs = [sg.RuleInput(r.weekday, r.start_time, r.end_time, r.timezone) for r in rules]
    exceptions_by_day: dict[dt.date, list[sg.ExceptionInput]] = defaultdict(list)
    for e in exceptions:
        exceptions_by_day[e.date].append(sg.ExceptionInput(e.type, e.start_time, e.end_time, e.timezone))

    # Availability windows do not depend on the event type: work them out once.
    days = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
    windows_by_day = {
        day: sg.apply_exceptions_for_date(
            day, sg.base_windows_for_date(day, rule_inputs), exceptions_by_day.get(day, [])
        )
        for day in days
    }

    # 5. Per event type: generate, upsert, reconcile, commit (one transaction each).
    for event_type in event_types:
        before = event_type.buffer_before_minutes
        after = event_type.buffer_after_minutes
        generated: set[tuple[datetime, datetime]] = set()
        rows: list[dict[str, Any]] = []

        for day in days:
            for slot in sg.split_into_slots(windows_by_day[day], event_type.duration_minutes, before, after):
                if not range_start <= slot.start <= range_end:
                    continue
                if slot.start <= now:
                    continue
                if sg.overlaps_booked(slot, booked, before, after):
                    continue
                key = (to_db(slot.start), to_db(slot.end))
                if key in generated:
                    # The same slot can come from two neighbouring dates when rules
                    # use different zones. A duplicate inside one INSERT ... ON
                    # CONFLICT statement is an error in PostgreSQL, so skip it.
                    continue
                generated.add(key)
                rows.append(
                    {
                        "id": new_slot_id(),
                        "host_id": host_id,
                        "event_type_id": event_type.id,
                        "start_at": key[0],
                        "end_at": key[1],
                    }
                )

        async with session_factory() as session:
            await slot_repository.upsert_available(session, rows)
            existing = await slot_repository.find_reconcilable(
                session, event_type.id, to_db(range_start), to_db(range_end), to_db(now)
            )
            stale = [row.id for row in existing if (row.start_at, row.end_at) not in generated]
            await slot_repository.mark_blocked(session, stale)
            await session.commit()

        logger.info(
            "Regenerated slots host=%s event_type=%s available=%s blocked=%s",
            host_id, event_type.id, len(rows), len(stale),
        )

    # D8: a deactivated event type's open slots must not stay bookable by id.
    async with session_factory() as session:
        await slot_repository.block_available_for_inactive_event_types(session, host_id, to_db(now))
        await session.commit()