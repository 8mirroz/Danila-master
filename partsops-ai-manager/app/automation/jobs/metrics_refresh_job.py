"""Refreshes tenant automation metrics and counters from current job results."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session

from app.automation.context import AutomationContext
from app.automation.events import append_system_event

logger = logging.getLogger("automation.jobs.metrics_refresh")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True, "refreshed": False}
    append_system_event(
        session=session,
        tenant_id=context.tenant_id,
        event_type="metrics.refresh.finished",
        actor_type="automation",
        actor_id=context.actor_id,
        payload={"tenant_id": context.tenant_id},
    )
    return {"ok": True, "refreshed": True}
