"""Validates candidate suite and emits supplier-side quote request events."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.supplier_validate")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_ids = context.payload.get("request_ids") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "validated": 0, "skipped": len(request_ids)}

    validated = 0
    skipped = 0
    for req_id in request_ids:
        row = session.exec(
            select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == req_id)
        ).first()
        if not row:
            skipped += 1
            continue
        candidates = context.payload.get("candidates", {}).get(req_id, [])
        valid = bool(candidates)
        append_request_event(
            session=session,
            request_id=req_id,
            tenant_id=context.tenant_id,
            event_type=EventType.SUPPLIER_QUERIED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"valid": valid, "candidate_count": len(candidates)},
        )
        validated += 1
    return {"ok": True, "validated": validated, "skipped": skipped}
