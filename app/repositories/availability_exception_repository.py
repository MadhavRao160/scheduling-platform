"""Data access for `availability_exceptions`. Every lookup is scoped to the user."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_exception import AvailabilityException


async def list_by_user(
    session: AsyncSession, user_id: int
) -> Sequence[AvailabilityException]:
    """Ordered by date. Within a day, full-day blocks (no start time) first,
    then by start time."""
    result = await session.scalars(
        select(AvailabilityException)
        .where(AvailabilityException.user_id == user_id)
        .order_by(
            AvailabilityException.date,
            AvailabilityException.start_time.asc().nulls_first(),
            AvailabilityException.id,
        )
    )
    return result.all()


async def get_for_user(
    session: AsyncSession, user_id: int, exception_id: int
) -> AvailabilityException | None:
    return await session.scalar(
        select(AvailabilityException).where(
            AvailabilityException.id == exception_id,
            AvailabilityException.user_id == user_id,
        )
    )


async def save(
    session: AsyncSession, exception: AvailabilityException
) -> AvailabilityException:
    """Flush pending changes and reload database-filled columns. Not a commit."""
    await session.flush()
    await session.refresh(exception)
    return exception


async def add(
    session: AsyncSession, exception: AvailabilityException
) -> AvailabilityException:
    session.add(exception)
    return await save(session, exception)


async def delete(session: AsyncSession, exception: AvailabilityException) -> None:
    await session.delete(exception)
    await session.flush()