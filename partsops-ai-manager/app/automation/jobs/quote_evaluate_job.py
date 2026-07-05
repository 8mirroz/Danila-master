"""Evaluates collected offers and emits manager approval/rejection events."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.quote_evaluate")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    items = context.payload.get("items") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "evaluated": 0, "skipped": len(items)}

    evaluated = 0
    skipped = 0
    for item in items:
        request_id = item.get("request_id")
        if not request_id:
            skipped += 1
            continue
        row = session.exec(
            select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == request_id)
        ).first()
        if not row:
            skipped += 1
            continue
        decision = item.get("decision")
        event_type = EventType.MANAGER_APPROVED if decision == "approve" else EventType.MANAGER_REJECTED
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=event_type,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"decision": decision, "score": item.get("score")},
        )
        evaluated += 1
    return {"ok": True, "evaluated": evaluated, "skipped": skipped}
