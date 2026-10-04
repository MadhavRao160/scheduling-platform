"""Data access for the `event_types` table.

Every lookup is scoped to a host. A row belonging to another host is never
loaded — the query itself excludes it — so the service sees it exactly as it
would see a row that does not exist.
"""

from collections.abc import Sequence

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_type import EventType
from sqlalchemy.orm import joinedload


async def list_by_host(session: AsyncSession, host_id: int) -> Sequence[EventType]:
    """Newest first, inactive ones included — this is the host's management view.
    id breaks ties between rows created in the same millisecond."""
    result = await session.scalars(
        select(EventType)
        .where(EventType.host_id == host_id)
        .order_by(EventType.created_at.desc(), EventType.id.desc())
    )
    return result.all()


async def get_for_host(
    session: AsyncSession, host_id: int, event_type_id: int
) -> EventType | None:
    return await session.scalar(
        select(EventType).where(
            EventType.id == event_type_id,
            EventType.host_id == host_id,
        )
    )


async def slug_taken(
    session: AsyncSession,
    host_id: int,
    slug: str,
    exclude_id: int | None = None,
) -> bool:
    """Whether this host already has an event type with this slug.

    exclude_id leaves one row out of the check, so that an event type being
    updated does not collide with its own current slug.
    """
    condition = (EventType.host_id == host_id) & (EventType.slug == slug)
    if exclude_id is not None:
        condition = condition & (EventType.id != exclude_id)
    return bool(await session.scalar(select(exists().where(condition))))


async def save(session: AsyncSession, event_type: EventType) -> EventType:
    """Flush pending changes and reload database-filled columns. Not a commit."""
    await session.flush()
    await session.refresh(event_type)
    return event_type


async def add(session: AsyncSession, event_type: EventType) -> EventType:
    session.add(event_type)
    return await save(session, event_type)


async def delete(session: AsyncSession, event_type: EventType) -> None:
    await session.delete(event_type)
    await session.flush()

async def get_active_with_host(
    session: AsyncSession, host_id: int, slug: str
) -> EventType | None:
    """An active event type with its host, loaded in a single query.

    Missing, inactive and host-less all come back as None — the query simply
    finds nothing — so callers cannot tell them apart.
    """
    return await session.scalar(
        select(EventType)
        .options(joinedload(EventType.host, innerjoin=True))
        .where(
            EventType.host_id == host_id,
            EventType.slug == slug,
            EventType.is_active.is_(True),
        )
    )