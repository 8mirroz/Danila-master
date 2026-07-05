"""Deduplicates concurrent intake items using an idempotency check."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.intake_dedupe")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    items = context.payload.get("items") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "processed": 0, "deduped": 0}

    processed = 0
    deduped = 0
    seen: set = set()
    rows_to_delete = []
    for item in items:
        request_id = item.get("request_id")
        idempotency_key = item.get("idempotency_key")
        if not request_id or not idempotency_key:
            continue
        key = (context.tenant_id, request_id, idempotency_key)
        if key in seen:
            deduped += 1
            rows_to_delete.append(request_id)
            continue
        seen.add(key)
        processed += 1

    for request_id in rows_to_delete:
        dup = session.exec(
            select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == request_id)
        ).first()
        if dup:
            session.delete(dup)
            append_request_event(
                session=session,
                request_id=request_id,
                tenant_id=context.tenant_id,
                event_type=EventType.IDEMPOTENCY_HIT,
                actor_type="automation",
                actor_id=context.actor_id,
                payload={"dedupe": True},
            )
    session.commit()
    return {"ok": True, "processed": processed, "deduped": deduped}
