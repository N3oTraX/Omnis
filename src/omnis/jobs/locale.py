"""
Locale Job - Stub implementation.

This is a placeholder for locale and keyboard configuration.
"""

from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult


class LocaleJob(BaseJob):
    """
    Locale and keyboard configuration job stub.

    This is a placeholder implementation that will be replaced
    with actual locale configuration logic.
    """

    name = "locale"
    description = "Locale and keyboard configuration (stub)"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the locale job."""
        super().__init__(config)

    def run(self, context: JobContext) -> JobResult:
        """
        Execute the locale configuration job.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success (stub always succeeds)
        """
        context.report_progress(0, "Configuring locale...")
        context.report_progress(50, "Setting keyboard layout...")
        context.report_progress(100, "Locale configuration complete")

        return JobResult.ok("Locale configured (stub)")

    def estimate_duration(self) -> int:
        """
        Estimate execution time in seconds.

        Returns:
            Estimated duration (placeholder value)
        """
        return 10
