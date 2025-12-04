"""Finished Job - Stub implementation."""

from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult


class FinishedJob(BaseJob):
    """Installation completion job stub."""

    name = "finished"
    description = "Installation completed (stub)"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(100, "Done")
        return JobResult.ok("Installation finished (stub)")

    def estimate_duration(self) -> int:
        return 5
