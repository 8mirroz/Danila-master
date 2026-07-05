"""
Automation errors — typed failure surface for jobs and pipelines.
"""
from __future__ import annotations


class AutomationError(Exception):
    """Base class for automation-layer failures."""

    def __init__(self, message: str, *, code: str = "automation_error", **context):
        super().__init__(message)
        self.code = code
        self.context = context

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": str(self),
            "context": self.context,
        }


class JobAbortedError(AutomationError):
    def __init__(self, message: str, **context):
        super().__init__(message, code="job_aborted", **context)


class BudgetExceededError(AutomationError):
    def __init__(self, message: str, **context):
        super().__init__(message, code="budget_exceeded", **context)


class PolicyViolationError(AutomationError):
    def __init__(self, message: str, **context):
        super().__init__(message, code="policy_violation", **context)


class EvidenceMissingError(AutomationError):
    def __init__(self, message: str, **context):
        super().__init__(message, code="evidence_missing", **context)


class StateGuardError(AutomationError):
    def __init__(self, message: str, **context):
        super().__init__(message, code="state_guard", **context)
