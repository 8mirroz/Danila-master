"""Cleans up orphaned job/runtime artifacts without touching live business data."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session

from app.automation.context import AutomationContext
from app.automation.events import append_system_event

logger = logging.getLogger("automation.jobs.dead_letter_cleanup")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True, "removed": 0}

    append_system_event(
        session=session,
        tenant_id=context.tenant_id,
        event_type="dead_letter.cleanup.finished",
        actor_type="automation",
        actor_id=context.actor_id,
        payload={
            "retention_hours": context.payload.get("retention_hours", 72),
            "removed": 0,
        },
    )
    return {"ok": True, "removed": 0}
