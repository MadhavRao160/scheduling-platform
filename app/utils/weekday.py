"""Weekday conversion.

The schema stores weekdays as 0 = Sunday … 6 = Saturday. That matches neither
Python's date.weekday() (0 = Monday) nor ISO weekday (1 = Monday … 7 = Sunday),
so the conversion lives here, once. Pure: no I/O.
"""

import datetime


def schema_weekday(day: datetime.date) -> int:
    """The schema's weekday number for a calendar date. Sunday -> 0."""
    return (day.weekday() + 1) % 7