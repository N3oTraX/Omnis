"""Packages Job - Stub implementation."""

from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult


class PackagesJob(BaseJob):
    """Package selection job stub."""

    name = "packages"
    description = "Package selection (stub)"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(100, "Done")
        return JobResult.ok("Packages selected (stub)")

    def estimate_duration(self) -> int:
        return 10
