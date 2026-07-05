"""Creates `PartRequest` rows from queued intake items and emits REQUEST_RECEIVED."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event
from models import PartRequest, RequestPriority, RequestState, EventType

logger = logging.getLogger("automation.jobs.intake_collect")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    items = context.payload.get("items") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "collected": 0, "skipped": len(items)}

    collected = 0
    skipped = 0
    for item in items:
        text = item.get("text") or ""
        if not text.strip():
            skipped += 1
            continue
        idempotency_key = item.get("idempotency_key") or f"INT-{hash(text)}"  # noqa: S324
        existing = session.exec(
            select(PartRequest)
            .where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.idempotency_key == idempotency_key)
        ).first()
        if existing:
            skipped += 1
            continue
        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        row = PartRequest(
            tenant_id=context.tenant_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            source=item.get("source", "api"),
            status=RequestState.NEW,
            priority=item.get("priority") or RequestPriority.NORMAL,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.REQUEST_RECEIVED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"source": row.source, "priority": row.priority},
        )
        collected += 1
    return {"ok": True, "collected": collected, "skipped": skipped}
