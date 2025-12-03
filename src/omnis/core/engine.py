"""
Omnis Engine - Core installation orchestrator.

Handles configuration loading, job management, and execution pipeline.
Runs in root context, separated from UI process.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from omnis.jobs.base import BaseJob, JobContext, JobResult, JobStatus


class BrandingColors(BaseModel):
    """Color scheme for UI branding."""

    primary: str = "#7C3AED"
    secondary: str = "#A78BFA"
    accent: str = "#F59E0B"
    background: str = "#1F2937"
    surface: str = "#374151"
    text: str = "#F9FAFB"
    text_muted: str = "#9CA3AF"


class BrandingAssets(BaseModel):
    """Asset paths for UI branding."""

    logo: str = ""
    logo_text: str = ""
    background: str = ""
    icon: str = ""


class BrandingStrings(BaseModel):
    """Customizable UI strings."""

    welcome_title: str = "Welcome"
    welcome_subtitle: str = ""
    install_button: str = "Install"
    finished_title: str = "Installation Complete"
    finished_message: str = ""


class BrandingConfig(BaseModel):
    """Complete branding configuration."""

    name: str = "Linux"
    version: str = ""
    edition: str = ""
    colors: BrandingColors = Field(default_factory=BrandingColors)
    assets: BrandingAssets = Field(default_factory=BrandingAssets)
    strings: BrandingStrings = Field(default_factory=BrandingStrings)


class JobDefinition(BaseModel):
    """Job definition from configuration."""

    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class AdvancedConfig(BaseModel):
    """Advanced engine configuration."""

    log_level: str = "info"
    log_file: str = "/var/log/omnis-install.log"
    ipc_socket: str = "/run/omnis/ipc.sock"
    job_timeout: int = 3600
    debug_mode: bool = False


class OmnisConfig(BaseModel):
    """Root configuration model."""

    version: str = "1.0"
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    jobs: list[JobDefinition | str] = Field(default_factory=list)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)

    def normalize_jobs(self) -> list[JobDefinition]:
        """Convert all job entries to JobDefinition objects."""
        normalized: list[JobDefinition] = []
        for job in self.jobs:
            if isinstance(job, str):
                normalized.append(JobDefinition(name=job))
            else:
                normalized.append(job)
        return normalized


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""

    pass


class JobLoadError(Exception):
    """Raised when a job cannot be loaded."""

    pass


@dataclass
class EngineState:
    """Current state of the engine."""

    current_job_index: int = -1
    total_jobs: int = 0
    is_running: bool = False
    is_finished: bool = False
    last_error: str | None = None


@dataclass
class Engine:
    """
    Core installation engine.

    Responsibilities:
    - Load and validate configuration
    - Instantiate and manage jobs
    - Execute jobs sequentially
    - Report progress to UI via callbacks

    Example:
        engine = Engine.from_config_file("omnis.yaml")
        engine.on_progress = lambda job, pct, msg: print(f"{job}: {pct}%")
        result = engine.run_all()
    """

    config: OmnisConfig
    jobs: list[BaseJob] = field(default_factory=list)
    state: EngineState = field(default_factory=EngineState)

    # Callbacks
    on_job_start: Any | None = None  # (job_name: str) -> None
    on_job_progress: Any | None = None  # (job_name: str, percent: int, msg: str) -> None
    on_job_complete: Any | None = None  # (job_name: str, result: JobResult) -> None
    on_error: Any | None = None  # (job_name: str, error: str) -> None

    @classmethod
    def from_config_file(cls, path: str | Path) -> "Engine":
        """
        Create an Engine instance from a YAML configuration file.

        Args:
            path: Path to omnis.yaml configuration file

        Returns:
            Configured Engine instance

        Raises:
            ConfigurationError: If config is invalid or missing
        """
        config_path = Path(path)

        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        try:
            with config_path.open("r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML syntax: {e}") from e

        if raw_config is None:
            raise ConfigurationError("Configuration file is empty")

        try:
            config = OmnisConfig.model_validate(raw_config)
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}") from e

        engine = cls(config=config)
        engine._load_jobs()

        return engine

    def _load_jobs(self) -> None:
        """
        Load and instantiate all jobs defined in configuration.

        Jobs are loaded from omnis.jobs.<name> module.
        """
        self.jobs = []
        job_definitions = self.config.normalize_jobs()

        for job_def in job_definitions:
            job = self._load_single_job(job_def)
            self.jobs.append(job)

        self.state.total_jobs = len(self.jobs)

    def _load_single_job(self, job_def: JobDefinition) -> BaseJob:
        """
        Load a single job by name.

        Args:
            job_def: Job definition with name and config

        Returns:
            Instantiated job

        Raises:
            JobLoadError: If job cannot be loaded
        """
        # TODO: Implement dynamic job loading from omnis.jobs.<name>
        # For now, return a placeholder
        # In production:
        # module = importlib.import_module(f"omnis.jobs.{job_def.name}")
        # job_class = getattr(module, "Job")
        # return job_class(config=job_def.config)

        from omnis.jobs.base import BaseJob, JobContext, JobResult

        class PlaceholderJob(BaseJob):
            """Placeholder job for skeleton implementation."""

            def __init__(self, name: str, config: dict[str, Any]) -> None:
                super().__init__(config)
                self.name = name
                self.description = f"Placeholder for {name}"

            def run(self, context: JobContext) -> JobResult:
                return JobResult.ok(f"Job {self.name} completed (placeholder)")

            def estimate_duration(self) -> int:
                return 10

        return PlaceholderJob(name=job_def.name, config=job_def.config)

    def get_branding(self) -> BrandingConfig:
        """Get branding configuration for UI."""
        return self.config.branding

    def get_job_names(self) -> list[str]:
        """Get ordered list of job names."""
        return [job.name for job in self.jobs]

    def run_all(self, context: JobContext | None = None) -> bool:
        """
        Execute all jobs sequentially.

        Args:
            context: Execution context (created if not provided)

        Returns:
            True if all jobs succeeded, False otherwise
        """
        if context is None:
            context = JobContext()

        self.state.is_running = True
        self.state.is_finished = False
        self.state.last_error = None

        for index, job in enumerate(self.jobs):
            self.state.current_job_index = index

            result = self._run_single_job(job, context)

            if not result.success:
                self.state.last_error = result.message
                self.state.is_running = False
                return False

        self.state.is_running = False
        self.state.is_finished = True
        return True

    def _run_single_job(self, job: BaseJob, context: JobContext) -> JobResult:
        """
        Execute a single job with progress reporting.

        Args:
            job: Job to execute
            context: Execution context

        Returns:
            Job result
        """
        job.status = JobStatus.RUNNING

        if self.on_job_start:
            self.on_job_start(job.name)

        # Set up progress callback
        def progress_callback(percent: int, message: str) -> None:
            if self.on_job_progress:
                self.on_job_progress(job.name, percent, message)

        context.on_progress = progress_callback
        context.config = job._config

        # Validate
        validation = job.validate(context)
        if not validation.success:
            job.status = JobStatus.FAILED
            if self.on_error:
                self.on_error(job.name, validation.message)
            return validation

        # Execute
        try:
            result = job.run(context)
        except Exception as e:
            result = JobResult.fail(str(e))
            job.status = JobStatus.FAILED
            if self.on_error:
                self.on_error(job.name, str(e))
            return result
        finally:
            job.cleanup(context)

        # Update status
        job.status = JobStatus.COMPLETED if result.success else JobStatus.FAILED

        if self.on_job_complete:
            self.on_job_complete(job.name, result)

        return result

    def get_progress(self) -> tuple[int, int]:
        """
        Get current progress as (current_job, total_jobs).

        Returns:
            Tuple of (current job index, total jobs)
        """
        return (self.state.current_job_index + 1, self.state.total_jobs)
