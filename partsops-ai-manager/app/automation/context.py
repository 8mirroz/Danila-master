"""
AutomationContext — single bag-of-context all jobs require.

Every job call signature is `(context: AutomationContext) -> JobResult`.
The context carries tenant identity, actor identity, dry-run flag,
correlation id (for log tracing), and idempotency key (for repeat-safe
executions).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


VALID_ROLES = {"admin", "manager", "finance", "system", "agent"}


@dataclass
class AutomationContext:
    tenant_id: str
    actor_id: str = "system"
    actor_type: str = "system"
    role: str = "system"

    request_id: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: f"CORR-{uuid.uuid4().hex[:12]}")
    idempotency_key: Optional[str] = None
    dry_run: bool = False

    # Loose bag for job-specific data (old_request, fleet_id, etc.).
    payload: Dict[str, Any] = field(default_factory=dict)

    # Optional limits / batch knobs.
    limit: Optional[int] = None
    offset: int = 0

    def child(self, **overrides) -> "AutomationContext":
        """Clone this context with overrides. Useful for nested pipeline steps."""
        merged = {
            "tenant_id": self.tenant_id,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "role": self.role,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "dry_run": self.dry_run,
            "payload": dict(self.payload),
            "limit": self.limit,
            "offset": self.offset,
        }
        merged.update(overrides)
        return AutomationContext(**merged)


def build_context(
    tenant_id: str = "default",
    actor_id: str = "system",
    role: str = "system",
    request_id: Optional[str] = None,
    dry_run: bool = False,
    idempotency_key: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **payload,
) -> AutomationContext:
    """Convenience builder. Raises ValueError on missing tenant_id."""
    if not tenant_id:
        raise ValueError("tenant_id is required for any automation context")
    if role not in VALID_ROLES:
        raise ValueError(
            f"role '{role}' not in {sorted(VALID_ROLES)}"
        )
    return AutomationContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        role=role,
        request_id=request_id,
        dry_run=dry_run,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id or f"CORR-{uuid.uuid4().hex[:12]}",
        payload=payload,
    )
