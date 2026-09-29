from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings

# One engine per process. It owns the connection pool; creating more than one
# would mean several pools competing for the same database.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

# A callable that produces a new AsyncSession. Exposed at module level so any
# caller can obtain a session, not only code running inside a request.
session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request.

    Rolls back if the request raised, and always closes. It never commits —
    committing is the service's responsibility, so that the point at which the
    transaction becomes durable is visible in the service's own code.
    """
    session = session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()