"""Applies margin/policy checks over evaluated quotes."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.quote_policy_check")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    items = context.payload.get("items") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "checked": 0, "skipped": len(items)}

    checked = 0
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
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.MARGIN_POLICY_CHECKED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={
                "acceptable": item.get("acceptable", False),
                "margin_percent": item.get("margin_percent"),
            },
        )
        checked += 1
    return {"ok": True, "checked": checked, "skipped": skipped}
