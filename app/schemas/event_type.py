"""Request and response shapes for /api/event-types."""

from enum import StrEnum
from typing import Annotated
from pydantic import Field, model_validator
from app.schemas.common import CamelModel, Slug, UtcDatetime

class LocationType(StrEnum):
    """Stored as TEXT; the allowed values are enforced here, at the boundary,
    so they also appear in the OpenAPI document."""

    ONLINE = "online"
    IN_PERSON = "in-person"

Title = Annotated[str, Field(min_length=1, max_length=200)]
Description = Annotated[str, Field(max_length=1000)]
DurationMinutes = Annotated[int, Field(ge=15, le=120)]
BufferMinutes = Annotated[int, Field(ge=0, le=120)]

class CreateEventTypeRequest(CamelModel):
    """Body of POST /api/event-types."""

    title: Title
    description: Description | None = None
    duration_minutes: DurationMinutes = 30
    is_active: bool = True
    location_type: LocationType = LocationType.ONLINE
    location_value: str | None = None
    buffer_before_minutes: BufferMinutes = 0
    buffer_after_minutes: BufferMinutes = 0
    slug: Slug | None = None  # derived from the title by the service when omitted


class UpdateEventTypeRequest(CamelModel):
    """Body of PATCH /api/event-types/{event_type_id}.
    Every field optional. An empty body is accepted and changes nothing.
    Only description and locationValue may be set to null — every other
    column is NOT NULL, so null could never be a valid value for it.
    """

    title: Title | None = None
    description: Description | None = None
    duration_minutes: DurationMinutes | None = None
    is_active: bool | None = None
    location_type: LocationType | None = None
    location_value: str | None = None
    buffer_before_minutes: BufferMinutes | None = None
    buffer_after_minutes: BufferMinutes | None = None
    slug: Slug | None = None

    _NULLABLE = frozenset({"description", "location_value"})

    @model_validator(mode="after")
    def _reject_null_on_required_columns(self) -> "UpdateEventTypeRequest":
        nulls = sorted(
            field
            for field in self.model_fields_set
            if getattr(self, field) is None and field not in self._NULLABLE
        )
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")
        return self


class EventTypeResponse(CamelModel):
    """The host's full view of an event type — inactive ones included."""

    id: int
    host_id: int
    title: str
    description: str | None
    slug: str
    duration_minutes: int
    is_active: bool
    location_type: LocationType
    location_value: str | None
    buffer_before_minutes: int
    buffer_after_minutes: int
    created_at: UtcDatetime
    updated_at: UtcDatetime

# ---------------------------------------------------------------- Public view


class PublicEventTypeSummary(CamelModel):
    """The five event-type fields an invitee may see. Buffers, isActive,
    locationValue and timestamps are deliberately left out."""

    id: int
    title: str
    description: str | None
    duration_minutes: int
    location_type: LocationType


class PublicHost(CamelModel):
    name: str
    email: str


class PublicEventTypeResponse(CamelModel):
    event_type: PublicEventTypeSummary
    host: PublicHost