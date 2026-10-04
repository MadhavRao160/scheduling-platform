"""Request and response shapes for /api/availability."""

import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from app.schemas.common import HHMM, CamelModel, TimezoneStr, UtcDatetime

Weekday = Annotated[int, Field(ge=0, le=6, description="0 = Sunday … 6 = Saturday")]

# ---------------------------------------------------------------- Rules

class AvailabilityRuleFields(CamelModel):
    """A complete availability rule, with its one cross-field rule:
    endTime must be after startTime.

    Used in two places:
    - as the POST body, where the client sends every field;
    - by the service on PATCH, to check the stored rule combined with the
      changes. Checking the changes alone is not enough — sending only
      {"endTime": "08:00"} looks valid, but turns a 09:00–17:00 rule into
      09:00–08:00.
    """

    weekday: Weekday
    start_time: HHMM
    end_time: HHMM
    is_active: bool = True
    timezone: TimezoneStr = "UTC"

    @model_validator(mode="after")
    def _end_after_start(self) -> "AvailabilityRuleFields":
        if self.end_time <= self.start_time:
            raise ValueError("endTime must be after startTime")
        return self


class CreateAvailabilityRuleRequest(AvailabilityRuleFields):
    """Body of POST /api/availability/rules."""


class UpdateAvailabilityRuleRequest(CamelModel):
    """Body of PATCH /api/availability/rules/{rule_id}.

    Every field optional; an empty body changes nothing. No field may be null.
    The start/end ordering is not checked here — only the service can see the
    stored values it must be checked against.
    """

    weekday: Weekday | None = None
    start_time: HHMM | None = None
    end_time: HHMM | None = None
    is_active: bool | None = None
    timezone: TimezoneStr | None = None

    @model_validator(mode="after")
    def _reject_null(self) -> "UpdateAvailabilityRuleRequest":
        nulls = sorted(f for f in self.model_fields_set if getattr(self, f) is None)
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")
        return self


class AvailabilityRuleResponse(CamelModel):
    id: int
    user_id: int
    weekday: int
    start_time: str
    end_time: str
    is_active: bool
    timezone: str
    created_at: UtcDatetime
    updated_at: UtcDatetime

# ---------------------------------------------------------------- Exceptions


class ExceptionType(StrEnum):
    BLOCK_FULL_DAY = "BLOCK_FULL_DAY"
    BLOCK_PARTIAL = "BLOCK_PARTIAL"
    ADD_AVAILABLE_WINDOW = "ADD_AVAILABLE_WINDOW"


Reason = Annotated[str, Field(max_length=500)]


class _ExceptionCommon(CamelModel):
    """Fields every exception has, whatever its type."""

    date: datetime.date
    timezone: TimezoneStr = "UTC"
    reason: Reason | None = None


class FullDayBlock(_ExceptionCommon):
    """Unavailable all day. Has no time fields — sending one is rejected."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["BLOCK_FULL_DAY"]


class _TimedException(_ExceptionCommon):
    """An exception that covers a window within the day."""

    start_time: HHMM
    end_time: HHMM

    @model_validator(mode="after")
    def _end_after_start(self) -> "_TimedException":
        if self.end_time <= self.start_time:
            raise ValueError("endTime must be after startTime")
        return self


class PartialBlock(_TimedException):
    """Remove startTime–endTime from that day."""

    type: Literal["BLOCK_PARTIAL"]


class AddWindow(_TimedException):
    """Add startTime–endTime on that day."""

    type: Literal["ADD_AVAILABLE_WINDOW"]


# One of the three shapes, chosen by the value of `type`.
AvailabilityExceptionFields = Union[FullDayBlock, PartialBlock, AddWindow]

# Used by the service to check a complete exception (on PATCH, after combining
# the stored row with the changes) against the same three shapes.
exception_fields_adapter = TypeAdapter(
    Annotated[AvailabilityExceptionFields, Field(discriminator="type")]
)


class UpdateAvailabilityExceptionRequest(CamelModel):
    """Body of PATCH /api/availability/exceptions/{exception_id}.

    Every field optional; an empty body changes nothing. startTime, endTime
    and reason may be null — needed, for example, when switching to
    BLOCK_FULL_DAY. Whether the result is valid is checked by the service
    after combining with the stored row.
    """

    date: datetime.date | None = None
    type: ExceptionType | None = None
    start_time: HHMM | None = None
    end_time: HHMM | None = None
    timezone: TimezoneStr | None = None
    reason: Reason | None = None

    _NULLABLE = frozenset({"start_time", "end_time", "reason"})

    @model_validator(mode="after")
    def _reject_null_on_required_columns(self) -> "UpdateAvailabilityExceptionRequest":
        nulls = sorted(
            f
            for f in self.model_fields_set
            if getattr(self, f) is None and f not in self._NULLABLE
        )
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")
        return self


class AvailabilityExceptionResponse(CamelModel):
    id: int
    user_id: int
    date: datetime.date
    type: ExceptionType
    start_time: str | None
    end_time: str | None
    timezone: str
    reason: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime