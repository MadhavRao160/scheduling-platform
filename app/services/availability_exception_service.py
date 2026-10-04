"""Business rules for availability exceptions.

As with rules, a PATCH is combined with the stored row and the result is
checked as a whole — here against the three type-specific shapes.
"""

from pydantic import ValidationError
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, not_found
from app.models.availability_exception import AvailabilityException
from app.repositories import availability_exception_repository, user_repository
from app.schemas.availability import (
    AvailabilityExceptionFields,
    AvailabilityExceptionResponse,
    UpdateAvailabilityExceptionRequest,
    exception_fields_adapter,
)

_COLUMNS = ("date", "type", "start_time", "end_time", "timezone", "reason")


def _to_response(exception: AvailabilityException) -> AvailabilityExceptionResponse:
    return AvailabilityExceptionResponse.model_validate(exception)


def _describe(exc: ValidationError) -> str:
    """Turn the first validation error into one readable sentence."""
    error = exc.errors()[0]
    message = error["msg"].removeprefix("Value error, ")
    if error["type"] == "value_error":
        return message
    if error["type"] == "extra_forbidden":
        message = "not allowed for BLOCK_FULL_DAY"
    field = to_camel(str(error["loc"][-1])) if error["loc"] else ""
    return f"{field}: {message}" if field else message


async def _load_or_404(
    session: AsyncSession, user_id: int, exception_id: int
) -> AvailabilityException:
    exception = await availability_exception_repository.get_for_user(
        session, user_id, exception_id
    )
    if exception is None:
        raise not_found("Availability exception")
    return exception


async def list_exceptions(
    session: AsyncSession, user_id: int
) -> list[AvailabilityExceptionResponse]:
    rows = await availability_exception_repository.list_by_user(session, user_id)
    return [_to_response(r) for r in rows]


async def create_exception(
    session: AsyncSession, user_id: int, payload: AvailabilityExceptionFields
) -> AvailabilityExceptionResponse:
    if await user_repository.get_by_id(session, user_id) is None:
        raise not_found("User")

    exception = AvailabilityException(user_id=user_id, **payload.model_dump())
    await availability_exception_repository.add(session, exception)
    await session.commit()
    return _to_response(exception)


async def update_exception(
    session: AsyncSession,
    user_id: int,
    exception_id: int,
    payload: UpdateAvailabilityExceptionRequest,
) -> AvailabilityExceptionResponse:
    exception = await _load_or_404(session, user_id, exception_id)
    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        return _to_response(exception)

    if "type" in changes:
        changes["type"] = str(changes["type"])  # enum member -> plain text

    # Stored values, with the changes on top. Empty values are dropped, so a
    # full-day block is checked without time fields rather than with nulls.
    combined = {column: getattr(exception, column) for column in _COLUMNS}
    combined.update(changes)
    candidate = {key: value for key, value in combined.items() if value is not None}

    try:
        checked = exception_fields_adapter.validate_python(candidate)
    except ValidationError as exc:
        raise BadRequestError(_describe(exc))

    # Write every column from the checked result, so the row ends up exactly
    # matching a valid shape.
    for column in _COLUMNS:
        setattr(exception, column, getattr(checked, column, None))

    await availability_exception_repository.save(session, exception)
    await session.commit()
    return _to_response(exception)


async def delete_exception(
    session: AsyncSession, user_id: int, exception_id: int
) -> None:
    exception = await _load_or_404(session, user_id, exception_id)
    await availability_exception_repository.delete(session, exception)
    await session.commit()