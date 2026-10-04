"""Data access for `availability_rules`. Every lookup is scoped to the user."""

from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.availability_rule import AvailabilityRule

async def list_by_user(session: AsyncSession, user_id: int) -> Sequence[AvailabilityRule]:
    """Ordered by weekday, then start time, as the spec requires."""
    result = await session.scalars(
        select(AvailabilityRule)
        .where(AvailabilityRule.user_id == user_id)
        .order_by(
            AvailabilityRule.weekday,
            AvailabilityRule.start_time,
            AvailabilityRule.id,
        )
    )
    return result.all()

async def get_for_user(
    session: AsyncSession, user_id: int, rule_id: int
) -> AvailabilityRule | None:
    return await session.scalar(
        select(AvailabilityRule).where(
            AvailabilityRule.id == rule_id,
            AvailabilityRule.user_id == user_id,
        )
    )


async def save(session: AsyncSession, rule: AvailabilityRule) -> AvailabilityRule:
    """Flush pending changes and reload database-filled columns. Not a commit."""
    await session.flush()
    await session.refresh(rule)
    return rule


async def add(session: AsyncSession, rule: AvailabilityRule) -> AvailabilityRule:
    session.add(rule)
    return await save(session, rule)


async def delete(session: AsyncSession, rule: AvailabilityRule) -> None:
    await session.delete(rule)
    await session.flush()