"""Automation package — exposes the registry + runner for convenience imports."""

from app.automation.context import AutomationContext, build_context
from app.automation.errors import (
    AutomationError,
    JobAbortedError,
    BudgetExceededError,
    PolicyViolationError,
    EvidenceMissingError,
    StateGuardError,
)
from app.automation.registry import (
    JOB_REGISTRY,
    PIPELINE_REGISTRY,
    register_job,
    register_pipeline,
    get_job,
    list_jobs,
    list_pipelines,
)
from app.automation.runner import run_job, run_pipeline

__all__ = [
    "AutomationContext",
    "build_context",
    "AutomationError",
    "JobAbortedError",
    "BudgetExceededError",
    "PolicyViolationError",
    "EvidenceMissingError",
    "StateGuardError",
    "JOB_REGISTRY",
    "PIPELINE_REGISTRY",
    "register_job",
    "register_pipeline",
    "get_job",
    "list_jobs",
    "list_pipelines",
    "run_job",
    "run_pipeline",
]
