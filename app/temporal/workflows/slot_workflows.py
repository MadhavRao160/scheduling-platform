"""RegenerateHostSlotsWorkflow (Section 9.3).

Workflow code must be deterministic: no I/O, no clock, no randomness.
It only tells Temporal which activity to run, with what options.
"""

from temporalio import workflow

# The sandbox re-imports workflow modules on every run. Passing these through
# reuses the already-loaded modules instead of re-importing SQLAlchemy etc.
with workflow.unsafe.imports_passed_through():
    from app.temporal.activities.slot_activities import regenerate_host_slots_activity
    from app.temporal.inputs import RegenerateHostSlotsInput
    from app.temporal.options import ACTIVITY_RETRY_POLICY, ACTIVITY_START_TO_CLOSE


@workflow.defn
class RegenerateHostSlotsWorkflow:
    @workflow.run
    async def run(self, data: RegenerateHostSlotsInput) -> None:
        await workflow.execute_activity(
            regenerate_host_slots_activity,
            data,
            start_to_close_timeout=ACTIVITY_START_TO_CLOSE,
            retry_policy=ACTIVITY_RETRY_POLICY,
        )
