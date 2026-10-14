"""Activity options shared by every workflow (Section 9.2)."""

from datetime import timedelta

from temporalio.common import RetryPolicy

ACTIVITY_START_TO_CLOSE = timedelta(minutes=10)

# Temporal's default backoff: 1s, then doubling, capped at 100s. 3 attempts total.
ACTIVITY_RETRY_POLICY = RetryPolicy(maximum_attempts=3)
