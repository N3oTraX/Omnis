"""
Install Job - Stub implementation.

This is a placeholder for the actual installation job.
"""

from typing import Any

from omnis.jobs.base import BaseJob, JobContext, JobResult


class InstallJob(BaseJob):
    """
    Installation job stub.

    This is a placeholder implementation that will be replaced
    with the actual installation logic.
    """

    name = "install"
    description = "System installation (stub)"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the install job."""
        super().__init__(config)

    def run(self, context: JobContext) -> JobResult:
        """
        Execute the installation job.

        Args:
            context: Execution context

        Returns:
            JobResult indicating success (stub always succeeds)
        """
        context.report_progress(0, "Starting installation...")
        context.report_progress(50, "Installing system...")
        context.report_progress(100, "Installation complete")

        return JobResult.ok("Installation completed (stub)")

    def estimate_duration(self) -> int:
        """
        Estimate execution time in seconds.

        Returns:
            Estimated duration (placeholder value)
        """
        return 300  # 5 minutes estimate
