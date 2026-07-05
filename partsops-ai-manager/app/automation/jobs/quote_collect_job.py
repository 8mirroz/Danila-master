"""Collects incoming supplier offers/quotes and emits OFFER_RECEIVED."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.quote_collect")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    offers = context.payload.get("offers") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "collected": 0, "skipped": len(offers)}

    collected = 0
    skipped = 0
    for offer in offers:
        request_id = offer.get("request_id")
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
            event_type=EventType.OFFER_RECEIVED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={
                "offer_id": offer.get("offer_id"),
                "supplier_id": offer.get("supplier_id"),
                "amount": offer.get("amount"),
            },
        )
        collected += 1
    return {"ok": True, "collected": collected, "skipped": skipped}
