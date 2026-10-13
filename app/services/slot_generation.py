"""Pure slot-generation arithmetic (Part 2, Section 8).

Zero I/O: no database session, no HTTP client, no datetime.now().
Every function takes plain values and returns plain values.

Conventions
- TimeWindow is half-open: [start, end). 09:00-09:30 and 09:30-10:00 touch
  but do not overlap.
- A window is built in its local zone, checked, then converted to UTC at once.
  All arithmetic after that happens in UTC, because Python adds timedeltas to
  same-zone aware datetimes on the wall clock and ignores DST.
- DST: a local time inside the spring-forward gap does not exist, so the
  window is dropped. A time that occurs twice in the autumn uses the first
  occurrence (fold=0, Python's default).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.utils.weekday import schema_weekday

BLOCK_FULL_DAY = "BLOCK_FULL_DAY"
BLOCK_PARTIAL = "BLOCK_PARTIAL"
ADD_AVAILABLE_WINDOW = "ADD_AVAILABLE_WINDOW"


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: datetime
    end: datetime

    def overlaps(self, other: TimeWindow) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True, slots=True)
class RuleInput:
    weekday: int  # 0 = Sunday
    start_time: str  # "HH:mm"
    end_time: str
    timezone: str  # IANA name


@dataclass(frozen=True, slots=True)
class ExceptionInput:
    type: str  # BLOCK_FULL_DAY | BLOCK_PARTIAL | ADD_AVAILABLE_WINDOW
    start_time: str | None
    end_time: str | None
    timezone: str


# ---------------------------------------------------------------- local time


def parse_time_on_date(day: date, hhmm: str, tz: str) -> datetime:
    """Attach a wall-clock time to a date, built directly in `tz`."""
    hours, minutes = map(int, hhmm.split(":"))
    return datetime.combine(day, time(hours, minutes), tzinfo=ZoneInfo(tz))


def _exists(local: datetime) -> bool:
    """False when the wall-clock time falls in a spring-forward gap.

    zoneinfo never raises for a missing time; it silently picks an offset.
    A round trip local -> UTC -> local changes the clock reading only when
    the original time did not exist.
    """
    round_trip = local.astimezone(UTC).astimezone(local.tzinfo)
    return round_trip.replace(tzinfo=None) == local.replace(tzinfo=None)


def _local_window_to_utc(day: date, start: str, end: str, tz: str) -> TimeWindow | None:
    """One local window on `day` as UTC, or None if empty or not valid that day."""
    if start >= end:  # zero-padded "HH:mm" compares correctly as text
        return None
    local_start = parse_time_on_date(day, start, tz)
    local_end = parse_time_on_date(day, end, tz)
    if not (_exists(local_start) and _exists(local_end)):
        return None
    window = TimeWindow(local_start.astimezone(UTC), local_end.astimezone(UTC))
    return window if window.start < window.end else None


# ------------------------------------------------------------- weekly rules


def windows_for_weekday_rule(
    day: date, weekday: int, start: str, end: str, tz: str
) -> list[TimeWindow]:
    """[] unless `day` is the rule's weekday and the times are valid that day."""
    if schema_weekday(day) != weekday:
        return []
    window = _local_window_to_utc(day, start, end, tz)
    return [window] if window else []


def base_windows_for_date(day: date, rules: Iterable[RuleInput]) -> list[TimeWindow]:
    """Every active rule's contribution for `day`, merged."""
    windows: list[TimeWindow] = []
    for rule in rules:
        windows.extend(
            windows_for_weekday_rule(day, rule.weekday, rule.start_time, rule.end_time, rule.timezone)
        )
    return merge_windows(windows)


# ------------------------------------------------------- interval algebra


def merge_windows(windows: Iterable[TimeWindow]) -> list[TimeWindow]:
    """Sort by start; join windows that overlap or exactly touch."""
    merged: list[TimeWindow] = []
    for window in sorted(windows, key=lambda w: (w.start, w.end)):
        if merged and window.start <= merged[-1].end:
            last = merged[-1]
            merged[-1] = TimeWindow(last.start, max(last.end, window.end))
        else:
            merged.append(window)
    return merged


def subtract_windows(windows: Iterable[TimeWindow], block: TimeWindow) -> list[TimeWindow]:
    """Remove `block` from each window, keeping any left and right remainders."""
    result: list[TimeWindow] = []
    for window in windows:
        if not window.overlaps(block):
            result.append(window)
            continue
        if block.start > window.start:
            result.append(TimeWindow(window.start, block.start))
        if block.end < window.end:
            result.append(TimeWindow(block.end, window.end))
    return result


# ------------------------------------------------------------- exceptions


def apply_exceptions_for_date(
    day: date, base: Sequence[TimeWindow], exceptions: Sequence[ExceptionInput]
) -> list[TimeWindow]:
    """Apply one date's exceptions to that date's base windows.

    A full-day block wins outright. Otherwise added windows go in first and
    partial blocks are subtracted after, so a block always beats an add,
    whatever order the rows arrive in.
    """
    if any(e.type == BLOCK_FULL_DAY for e in exceptions):
        return []

    windows = list(base)
    for e in exceptions:
        if e.type == ADD_AVAILABLE_WINDOW and e.start_time and e.end_time:
            added = _local_window_to_utc(day, e.start_time, e.end_time, e.timezone)
            if added:
                windows.append(added)

    for e in exceptions:
        if e.type == BLOCK_PARTIAL and e.start_time and e.end_time:
            block = _local_window_to_utc(day, e.start_time, e.end_time, e.timezone)
            if block:
                windows = subtract_windows(windows, block)

    return merge_windows(windows)


# ------------------------------------------------------------------ slots


def split_into_slots(
    windows: Iterable[TimeWindow],
    duration_minutes: int,
    buffer_before_minutes: int,
    buffer_after_minutes: int,
) -> list[TimeWindow]:
    """Cut windows into meeting slots, exactly as Section 8.2 specifies.

    The fit test reserves duration + both buffers, but the cursor advances by
    the duration alone. So buffers are honoured only at window edges; between
    neighbouring slots they are enforced later, by overlaps_booked, once one
    of them is booked. See docs/DECISIONS.md.
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    duration = timedelta(minutes=duration_minutes)
    before = timedelta(minutes=buffer_before_minutes)
    total = duration + before + timedelta(minutes=buffer_after_minutes)

    slots: list[TimeWindow] = []
    for window in windows:
        cursor = window.start
        while cursor + total <= window.end:
            slot_start = cursor + before
            slots.append(TimeWindow(slot_start, slot_start + duration))
            cursor += duration  # stride is duration, NOT total
    return slots


def overlaps_booked(
    slot: TimeWindow,
    booked: Iterable[TimeWindow],
    buffer_before_minutes: int,
    buffer_after_minutes: int,
) -> bool:
    """Pad the candidate by its buffers, then test overlap with each booking."""
    padded = TimeWindow(
        slot.start - timedelta(minutes=buffer_before_minutes),
        slot.end + timedelta(minutes=buffer_after_minutes),
    )
    return any(padded.overlaps(b) for b in booked)