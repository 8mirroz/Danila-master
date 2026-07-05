"""Esscalates stalled requests when SLA or timeout thresholds are exceeded."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.escalate_stalled")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_ids = context.payload.get("request_ids") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "escalated": 0, "skipped": len(request_ids)}

    escalated = 0
    skipped = 0
    for request_id in request_ids:
        if not request_id:
            skipped += 1
            continue
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.STATE_CHANGED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"escalated": True, "reason": context.payload.get("reason", "timeout")},
        )
        escalated += 1
    return {"ok": True, "escalated": escalated, "skipped": skipped}
