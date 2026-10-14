"""One Temporal client per process, connected on first use.

Not connected at startup on purpose: if Temporal is down, the API must still
start and serve requests (Section 7.4).
"""

import asyncio

from temporalio.client import Client

from app.config.settings import settings

_client: Client | None = None
_lock = asyncio.Lock()


async def get_client() -> Client:
    """Return the shared client, connecting once. A failed connect is not cached."""
    global _client
    if _client is None:
        async with _lock:
            if _client is None:  # another request may have connected while we waited
                _client = await Client.connect(
                    settings.temporal_address, namespace=settings.temporal_namespace
                )
    return _client


def reset_client() -> None:
    """Forget the client, e.g. at shutdown or in tests."""
    global _client
    _client = None
