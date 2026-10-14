"""Booking request and response shapes (Part 2, Section 10)."""

import datetime
from typing import Self

from pydantic import EmailStr, Field, model_validator

from app.models.booking import BookingStatus
from app.schemas.common import CamelModel, UtcDatetime


# ------------------------------------------------------------------ requests


class BookingCreate(CamelModel):
    slot_id: str = Field(min_length=1)
    invitee_email: EmailStr
    invitee_name: str = Field(min_length=1, max_length=100)
    invitee_notes: str | None = None


class BookingListQuery(CamelModel):
    """GET /api/bookings filters. `from`/`to` are UTC dates, both inclusive."""

    status: BookingStatus | None = None
    from_: datetime.date | None = Field(default=None, alias="from")  # "from" is a Python keyword
    to: datetime.date | None = None

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.from_ and self.to and self.to < self.from_:
            raise ValueError("'to' must not be before 'from'")
        return self


# ----------------------------------------------------------------- responses


class BookingEventTypeSummary(CamelModel):
    id: int
    title: str
    slug: str


class BookingListItem(CamelModel):
    id: int
    status: BookingStatus
    invitee_email: str
    invitee_name: str
    invitee_notes: str | None
    start_at: UtcDatetime
    end_at: UtcDatetime
    event_type: BookingEventTypeSummary


class BookingListResponse(CamelModel):
    bookings: list[BookingListItem]


class BookingCreated(CamelModel):
    """meetLink and calendarEventId are absent by design: they do not exist yet."""

    id: int
    status: BookingStatus
    start_at: UtcDatetime
    end_at: UtcDatetime


class BookingCreateResponse(CamelModel):
    booking: BookingCreated
