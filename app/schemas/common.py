"""Shared schema building blocks.

Holds the response envelope every business endpoint returns, the error
envelope the exception handlers emit, and the base class that gives every
schema in the project its camelCase JSON surface.
"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict
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