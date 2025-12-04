"""Partition Job - Stub implementation."""

from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult


class PartitionJob(BaseJob):
    """Partitioning job stub."""

    name = "partition"
    description = "Disk partitioning (stub)"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(100, "Done")
        return JobResult.ok("Partitioning completed (stub)")

    def estimate_duration(self) -> int:
        return 60
