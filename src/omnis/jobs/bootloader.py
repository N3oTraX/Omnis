"""Bootloader Job - Stub implementation."""

from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult


class BootloaderJob(BaseJob):
    """Bootloader installation job stub."""

    name = "bootloader"
    description = "Bootloader installation (stub)"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(100, "Done")
        return JobResult.ok("Bootloader installed (stub)")

    def estimate_duration(self) -> int:
        return 30
