"""Fire-and-forget workflow starters (Section 7.4).

Called only after a successful commit. Never raises: any failure is logged at
ERROR and returns None, so a request whose transaction committed still succeeds.
The durability gap this leaves is closed later by the transactional outbox.
"""

import asyncio
import datetime as dt
import logging
import time
from typing import Any

from app.config.settings import settings
from app.config.temporal import get_client
from app.temporal.inputs import RegenerateHostSlotsInput
from app.temporal.workflows.slot_workflows import RegenerateHostSlotsWorkflow

logger = logging.getLogger(__name__)

START_TIMEOUT_SECONDS = 5


def _epoch_ms() -> int:
    return time.time_ns() // 1_000_000


async def _start(name: str, workflow_run: Any, arg: Any, workflow_id: str) -> str | None:
    """Connect + start within 5 seconds. Returns the workflow id, or None."""
    if not settings.temporal_enabled:
        logger.info("Temporal disabled; skipped %s id=%s", name, workflow_id)
        return None

    async def connect_and_start() -> None:
        client = await get_client()
        await client.start_workflow(
            workflow_run, arg, id=workflow_id, task_queue=settings.temporal_task_queue
        )

    try:
        await asyncio.wait_for(connect_and_start(), timeout=START_TIMEOUT_SECONDS)
    except Exception:
        # Connection refused, timeout, WorkflowAlreadyStartedError, anything.
        logger.exception("Failed to start %s id=%s", name, workflow_id)
        return None
    return workflow_id


async def start_regenerate_host_slots(
    host_id: int, from_date: dt.date | None = None, to_date: dt.date | None = None
) -> str | None:
    workflow_id = f"regenerate-host-slots-{host_id}-{_epoch_ms()}"
    data = RegenerateHostSlotsInput(
        host_id=host_id,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
    )
    return await _start("RegenerateHostSlotsWorkflow", RegenerateHostSlotsWorkflow.run, data, workflow_id)
