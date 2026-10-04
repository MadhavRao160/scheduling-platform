"""Data access for the `users` table.
The only place in the Users feature that builds queries. Functions take a
session and plain values, return models or simple values, and make no
decisions: a missing row comes back as None, and deciding that None means
"404" is the service's job. Nothing here commits — the service owns that.
"""

from collections.abc import Sequence
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


async def list_all(session: AsyncSession) -> Sequence[User]:
    result = await session.scalars(select(User).order_by(User.id))
    return result.all()


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def slug_exists(session: AsyncSession, slug: str) -> bool:
    return bool(await session.scalar(select(exists().where(User.slug == slug))))


async def save(session: AsyncSession, user: User) -> User:
    """Write pending changes to the database and reload the row.

    The flush sends the INSERT or UPDATE inside the current transaction; it is
    not a commit. The refresh reads back columns the database filled in —
    id, createdAt, updatedAt — which are otherwise unloaded, and touching an
    unloaded column in async code raises rather than quietly querying.
    """
    await session.flush()
    await session.refresh(user)
    return user


async def add(session: AsyncSession, user: User) -> User:
    session.add(user)
    return await save(session, user)


async def delete(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.flush()