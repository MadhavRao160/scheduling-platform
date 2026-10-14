"""Temporal worker: a separate process. Never imports the FastAPI app.

Run: uv run python -m app.temporal.worker
"""

import asyncio
import logging

from temporalio.worker import Worker

from app.config.settings import settings
from app.config.temporal import get_client
from app.database import engine
from app.temporal.activities.slot_activities import regenerate_host_slots_activity
from app.temporal.workflows.slot_workflows import RegenerateHostSlotsWorkflow


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    client = await get_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[RegenerateHostSlotsWorkflow],
        activities=[regenerate_host_slots_activity],
    )
    logging.info("Worker listening on task queue %r", settings.temporal_task_queue)
    try:
        await worker.run()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
