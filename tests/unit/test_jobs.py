"""Unit tests for Omnis Jobs."""

import pytest

from omnis.jobs.base import BaseJob, JobContext, JobResult, JobStatus


class TestJobResult:
    """Tests for JobResult class."""

    def test_ok_result(self) -> None:
        """Test successful result creation."""
        result = JobResult.ok("Success message")

        assert result.success is True
        assert result.message == "Success message"
        assert result.error_code == 0

    def test_fail_result(self) -> None:
        """Test failed result creation."""
        result = JobResult.fail("Error message", error_code=42)

        assert result.success is False
        assert result.message == "Error message"
        assert result.error_code == 42

    def test_result_with_data(self) -> None:
        """Test result with additional data."""
        result = JobResult.ok(data={"key": "value"})

        assert result.data == {"key": "value"}


class TestJobContext:
    """Tests for JobContext class."""

    def test_default_context(self) -> None:
        """Test default context values."""
        context = JobContext()

        assert context.target_root == "/mnt/target"
        assert context.selections == {}
        assert context.config == {}

    def test_progress_callback(self) -> None:
        """Test progress reporting."""
        progress_calls: list[tuple[int, str]] = []

        def on_progress(percent: int, message: str) -> None:
            progress_calls.append((percent, message))

        context = JobContext(on_progress=on_progress)
        context.report_progress(50, "Halfway there")

        assert progress_calls == [(50, "Halfway there")]

    def test_progress_clamped(self) -> None:
        """Test progress values are clamped to 0-100."""
        progress_calls: list[tuple[int, str]] = []

        def on_progress(percent: int, message: str) -> None:
            progress_calls.append((percent, message))

        context = JobContext(on_progress=on_progress)
        context.report_progress(-10, "")
        context.report_progress(150, "")

        assert progress_calls[0][0] == 0
        assert progress_calls[1][0] == 100


class ConcreteJob(BaseJob):
    """Concrete implementation for testing."""

    name = "test_job"
    description = "A test job"

    def run(self, context: JobContext) -> JobResult:
        context.report_progress(100, "Done")
        return JobResult.ok()

    def estimate_duration(self) -> int:
        return 5


class TestBaseJob:
    """Tests for BaseJob abstract class."""

    def test_job_initialization(self) -> None:
        """Test job initialization."""
        job = ConcreteJob(config={"key": "value"})

        assert job.name == "test_job"
        assert job.status == JobStatus.PENDING
        assert job._config == {"key": "value"}

    def test_job_run(self) -> None:
        """Test job execution."""
        job = ConcreteJob()
        context = JobContext()

        result = job.run(context)

        assert result.success is True

    def test_job_validation_default(self) -> None:
        """Test default validation passes."""
        job = ConcreteJob()
        context = JobContext()

        result = job.validate(context)

        assert result.success is True

    def test_job_repr(self) -> None:
        """Test job string representation."""
        job = ConcreteJob()

        assert "test_job" in repr(job)
        assert "PENDING" in repr(job)
