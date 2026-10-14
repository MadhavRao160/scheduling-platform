"""Workflow inputs shared by the API (starter), workflows and activities.

One dataclass per workflow, so fields can be added later without breaking
workflows already in flight. Dates travel as ISO strings ("YYYY-MM-DD").
No heavy imports here: workflow code imports this inside the sandbox.
"""

from dataclasses import dataclass


@dataclass
class RegenerateHostSlotsInput:
    host_id: int
    from_date: str | None = None
    to_date: str | None = None
