"""Public slot listing shapes (Part 2, Section 8.5)."""

import datetime
from typing import Self

from pydantic import Field, model_validator

from app.schemas.common import CamelModel, TimezoneStr, UtcDatetime

MAX_LISTING_DAYS = 62


class SlotListQuery(CamelModel):
    """Query string for the public slot listing.

    `from` and `to` are local calendar dates in `timezone` (the host's zone
    when omitted), both inclusive.
    """

    from_: datetime.date = Field(alias="from")  # "from" is a Python keyword
    to: datetime.date
    timezone: TimezoneStr | None = None

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.to < self.from_:
            raise ValueError("'to' must not be before 'from'")
        if (self.to - self.from_).days + 1 > MAX_LISTING_DAYS:
            raise ValueError(f"Date range must not exceed {MAX_LISTING_DAYS} days")
        return self


class SlotOut(CamelModel):
    id: str
    start_at: UtcDatetime
    end_at: UtcDatetime


class SlotDay(CamelModel):
    date: datetime.date  # local calendar date in the requested timezone
    slots: list[SlotOut]


class SlotListResponse(CamelModel):
    timezone: str
    days: list[SlotDay]