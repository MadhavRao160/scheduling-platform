"""Slot activities: the side-effecting half of RegenerateHostSlotsWorkflow."""

import datetime as dt

from temporalio import activity

from app.services import slot_service
from app.temporal.inputs import RegenerateHostSlotsInput


def _parse(value: str | None) -> dt.date | None:
    return dt.date.fromisoformat(value) if value else None


@activity.defn
async def regenerate_host_slots_activity(data: RegenerateHostSlotsInput) -> None:
    """Idempotent (unique key + upsert), so Temporal may safely retry it.

    Any exception propagates, which is what makes Temporal retry.
    """
    await slot_service.regenerate_host_slots(
        data.host_id, _parse(data.from_date), _parse(data.to_date)
    )
