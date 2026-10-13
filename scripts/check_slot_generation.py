"""Hand checks for app/services/slot_generation.py. Run: uv run python -m scripts.check_slot_generation"""

from datetime import UTC, date, datetime

from app.services.slot_generation import (
    ADD_AVAILABLE_WINDOW,
    BLOCK_FULL_DAY,
    BLOCK_PARTIAL,
    ExceptionInput,
    TimeWindow,
    apply_exceptions_for_date,
    merge_windows,
    overlaps_booked,
    split_into_slots,
    subtract_windows,
    windows_for_weekday_rule,
)


def utc(day: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=UTC)


def show(windows: list[TimeWindow]) -> list[str]:
    return [f"{w.start:%H:%M}-{w.end:%H:%M}" for w in windows]


def check(label: str, got: object, expected: object) -> None:
    status = "PASS" if got == expected else "FAIL"
    print(f"{status}  {label}: {got}")
    if got != expected:
        print(f"      expected: {expected}")


MON = date(2026, 8, 10)          # Monday  -> weekday 1
SPRING = date(2026, 3, 29)       # Sunday  -> weekday 0, London clocks 01:00 -> 02:00
AUTUMN = date(2026, 10, 25)      # Sunday  -> weekday 0, London clocks 02:00 -> 01:00

# 1. Section 8.2 worked example
window = TimeWindow(utc(MON, "09:00"), utc(MON, "12:00"))
check("8.2 worked example", show(split_into_slots([window], 30, 10, 5)),
      ["09:10-09:40", "09:40-10:10", "10:10-10:40", "10:40-11:10", "11:10-11:40"])

# 2. Wrong weekday gives nothing
check("wrong weekday", windows_for_weekday_rule(MON, 2, "09:00", "17:00", "UTC"), [])

# 3. 09:00-17:00 London either side of DST (UTC instants shift by one hour)
check("London summer (BST)", show(windows_for_weekday_rule(MON, 1, "09:00", "17:00", "Europe/London")),
      ["08:00-16:00"])
check("London winter (GMT)", show(windows_for_weekday_rule(date(2026, 11, 2), 1, "09:00", "17:00", "Europe/London")),
      ["09:00-17:00"])

# 4. Spring gap: 01:30 does not exist on 29 Mar in London -> no window
check("spring gap start", windows_for_weekday_rule(SPRING, 0, "01:30", "04:00", "Europe/London"), [])
check("spring normal day", show(windows_for_weekday_rule(SPRING, 0, "09:00", "17:00", "Europe/London")),
      ["08:00-16:00"])

# 5. Autumn repeat: 01:30 happens twice on 25 Oct -> first occurrence (BST, 00:30 UTC)
check("autumn repeat start", show(windows_for_weekday_rule(AUTUMN, 0, "01:30", "03:00", "Europe/London")),
      ["00:30-03:00"])

# 6. merge: touching windows join
check("merge touching", show(merge_windows([
    TimeWindow(utc(MON, "10:00"), utc(MON, "11:00")),
    TimeWindow(utc(MON, "09:00"), utc(MON, "10:00")),
])), ["09:00-11:00"])

# 7. subtract: block in the middle leaves two pieces; touching block changes nothing
base = [TimeWindow(utc(MON, "09:00"), utc(MON, "17:00"))]
check("subtract middle", show(subtract_windows(base, TimeWindow(utc(MON, "12:00"), utc(MON, "13:00")))),
      ["09:00-12:00", "13:00-17:00"])
check("subtract touching", show(subtract_windows(base, TimeWindow(utc(MON, "17:00"), utc(MON, "18:00")))),
      ["09:00-17:00"])

# 8. exceptions
full = ExceptionInput(BLOCK_FULL_DAY, None, None, "UTC")
partial = ExceptionInput(BLOCK_PARTIAL, "12:00", "13:00", "UTC")
add = ExceptionInput(ADD_AVAILABLE_WINDOW, "18:00", "19:00", "UTC")
add_overlapping_block = ExceptionInput(ADD_AVAILABLE_WINDOW, "12:00", "12:30", "UTC")
check("full-day wins", apply_exceptions_for_date(MON, base, [add, partial, full]), [])
check("partial + add", show(apply_exceptions_for_date(MON, base, [partial, add])),
      ["09:00-12:00", "13:00-17:00", "18:00-19:00"])
check("block beats add", show(apply_exceptions_for_date(MON, base, [partial, add_overlapping_block])),
      ["09:00-12:00", "13:00-17:00"])

# 9. overlaps_booked: after 09:40 is booked, both neighbours disappear (buffers 10/5)
booked = [TimeWindow(utc(MON, "09:40"), utc(MON, "10:10"))]
candidates = split_into_slots([window], 30, 10, 5)
kept = [c for c in candidates if not overlaps_booked(c, booked, 10, 5)]
check("after booking 09:40", show(kept), ["10:40-11:10", "11:10-11:40"])