"""Extracts structured part intents from raw intake text and emits PART_INTENT_EXTRACTED."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.intake_extract_intent")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_ids = context.payload.get("request_ids") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "extracted": 0, "skipped": len(request_ids)}

    extracted = 0
    skipped = 0
    for req_id in request_ids:
        row = session.exec(
            select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == req_id)
        ).first()
        if not row:
            skipped += 1
            continue
        append_request_event(
            session=session,
            request_id=req_id,
            tenant_id=context.tenant_id,
            event_type=EventType.PART_INTENT_EXTRACTED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"candidates": context.payload.get("candidates", {}).get(req_id, [])},
        )
        extracted += 1
    return {"ok": True, "extracted": extracted, "skipped": skipped}
