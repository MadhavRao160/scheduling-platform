"""Dependencies shared by routers.

`HostId` reads and checks the x-user-id header. `SessionDep` provides the
per-request database session. Both are written once here so every router
uses the same rules.
"""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.errors import BadRequestError


async def get_host_id(
    x_user_id: Annotated[str | None, Header(alias="x-user-id")] = None,
) -> int:
    """Return the host id from the x-user-id header.

    There is no authentication: this header identifies the host but does not
    prove anything. A missing, non-numeric or non-positive value is a 400.
    """
    try:
        host_id = int(x_user_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise BadRequestError("Missing or invalid x-user-id header")
    if host_id < 1:
        raise BadRequestError("Missing or invalid x-user-id header")
    return host_id


HostId = Annotated[int, Depends(get_host_id)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]