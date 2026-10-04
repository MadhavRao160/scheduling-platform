"""Shared schema building blocks.

Holds the response envelope every business endpoint returns, the error
envelope the exception handlers emit, and the base class that gives every
schema in the project its camelCase JSON surface.
"""

from functools import lru_cache
from typing import Annotated, Any, Generic, TypeVar
from zoneinfo import available_timezones
from datetime import datetime

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base for every schema in the project.

    Python attributes stay snake_case; the JSON surface is camelCase, matching
    the column naming in the database. `populate_by_name` lets an object also
    be built using the Python names, which is what the service layer does when
    it converts a model into a response.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ApiResponse(CamelModel, Generic[T]):
    """The success envelope: `{ "success": true, "data": ..., "message": ... }`
    Declared as a route's `response_model` so the generated OpenAPI document
    describes the real shape rather than an untyped object. `T` is whatever
    the endpoint returns inside `data` — a single item, a list, or None.
    """

    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorResponse(CamelModel):
    """The failure envelope: `{ "success": false, "message": ..., "details": [...] }`

    Emitted by the exception handlers, never returned from a router directly.
    `details` carries structured validation errors, or a traceback when the
    environment is development.
    """

    success: bool = False
    message: str
    details: list[Any] | None = None

@lru_cache
def _known_timezones() -> frozenset[str]:
    """Every IANA zone name zoneinfo can resolve. Computed once — it scans
    the timezone database, so it should not run on every request."""
    return frozenset(available_timezones())


def _validate_timezone(value: str) -> str:
    if value not in _known_timezones():
        raise ValueError(f"'{value}' is not a valid IANA timezone, e.g. 'Asia/Kolkata'")
    return value


TimezoneStr = Annotated[str, AfterValidator(_validate_timezone)]
"""A string that must be a real IANA timezone name.

Validated at the schema boundary because an unresolvable zone stored in the
database only fails much later, when something tries to turn local times into
real instants — far from where the bad value came in."""

def _format_utc(value: datetime) -> str:
    """Render a stored timestamp as ISO 8601, millisecond precision, with Z.
    Stored timestamps carry no zone; they are UTC by convention, so Z is
    correct to append."""
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


UtcDatetime = Annotated[datetime, PlainSerializer(_format_utc, return_type=str)]
"""A datetime that serialises as '2026-08-10T09:00:00.000Z'."""

Slug = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")]
"""A URL-safe identifier: lower-case letters, digits and hyphens, 1–100 long."""

HHMM = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
"""A 24-hour wall-clock time, exactly 'HH:mm' — '09:00', '17:30'.
Because the format is fixed-width, two values compare correctly as plain
text: '09:00' < '17:00'."""
