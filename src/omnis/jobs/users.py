"""Users Job - Stub implementation."""

from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult


class UsersJob(BaseJob):
    """User creation job stub."""

    name = "users"
    description = "User configuration (stub)"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(100, "Done")
        return JobResult.ok("Users configured (stub)")

    def estimate_duration(self) -> int:
        return 10
