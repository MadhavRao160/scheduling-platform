"""Liveness probe.

Deliberately outside the /api prefix and outside the standard response
envelope: a supervisor checking this endpoint wants a fixed, minimal shape.

It must not touch the database. A liveness probe answers "is this process
alive", not "is every dependency healthy" — staying green during a database
outage is what stops a supervisor restarting a perfectly healthy process over
a problem restarting cannot fix.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "status": "ok!",
        "timestamp": f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond // 1000:03d}Z",
    }