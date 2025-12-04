"""Omnis installation jobs."""

from omnis.jobs.base import BaseJob, JobContext, JobResult, JobStatus
from omnis.jobs.requirements import (
    RequirementCheck,
    RequirementsResult,
    RequirementStatus,
    SystemRequirementsChecker,
)
from omnis.jobs.welcome import WelcomeConfig, WelcomeJob, WelcomeState

__all__ = [
    # Base classes
    "BaseJob",
    "JobContext",
    "JobResult",
    "JobStatus",
    # Requirements
    "RequirementCheck",
    "RequirementsResult",
    "RequirementStatus",
    "SystemRequirementsChecker",
    # Jobs
    "WelcomeJob",
    "WelcomeConfig",
    "WelcomeState",
]
