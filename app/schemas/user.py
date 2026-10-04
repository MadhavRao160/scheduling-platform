"""Request and response shapes for /api/users.
Every validation rule for this endpoint group lives here. By the time the
service runs, the input is already well-formed.
"""

from typing import Annotated
from pydantic import EmailStr, Field, model_validator
from app.schemas.common import CamelModel, Slug, TimezoneStr, UtcDatetime

Name = Annotated[str, Field(min_length=1, max_length=100)]

class CreateUserRequest(CamelModel):
    """Body of POST /api/users."""
    email: EmailStr
    name: Name
    slug: Slug | None = None  # derived from name by the service when omitted
    timezone: TimezoneStr = "UTC"


class UpdateUserRequest(CamelModel):
    """Body of PATCH /api/users/{user_id}.
    Every field is optional, but the body as a whole must change something.
    Slug is not updatable, matching the spec's field list.
    """
    email: EmailStr | None = None
    name: Name | None = None
    timezone: TimezoneStr | None = None

    @model_validator(mode="after")
    def _require_a_change(self) -> "UpdateUserRequest":
        if not self.model_fields_set:
            raise ValueError("Provide at least one of email, name or timezone")

        nulls = sorted(f for f in self.model_fields_set if getattr(self, f) is None)
        if nulls:
            raise ValueError(f"These fields cannot be null: {', '.join(nulls)}")

        return self


class UserResponse(CamelModel):
    """What appears inside `data` for a user."""
    id: int
    email: str
    name: str
    slug: str
    timezone: str
    created_at: UtcDatetime
    updated_at: UtcDatetime