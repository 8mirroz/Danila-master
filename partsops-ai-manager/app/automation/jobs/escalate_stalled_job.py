"""Escalates stalled requests when SLA or timeout thresholds are exceeded."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session

from app.automation.context import AutomationContext
from app.automation.engines.escalation_engine import escalate

logger = logging.getLogger("automation.jobs.escalate_stalled")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_ids = context.payload.get("request_ids") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "escalated": 0, "skipped": len(request_ids)}

    escalated = 0
    skipped = 0
    reason = context.payload.get("reason", "timeout")

    for request_id in request_ids:
        if not request_id:
            skipped += 1
            continue
        result = escalate(
            {
                "request_id": request_id,
                "tenant_id": context.tenant_id,
                "reason": reason,
                "session": session,
                "actor_id": context.actor_id,
            }
        )
        if result.get("escalated"):
            escalated += 1
        else:
            skipped += 1
            logger.info(
                "escalate skipped for %s: %s",
                request_id,
                result.get("reason") or result.get("status"),
            )

    return {"ok": True, "escalated": escalated, "skipped": skipped}
