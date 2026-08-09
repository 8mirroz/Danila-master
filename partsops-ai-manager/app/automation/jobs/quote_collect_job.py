"""Collects incoming supplier offers/quotes and emits OFFER_RECEIVED.

Honesty:
- This job does **not** pull from external supplier APIs or the crawler.
- It only records offers provided in ``context.payload["offers"]``.
- Empty payload → partial, not a silent success that implies market coverage.
"""
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
        return {
            "ok": True,
            "dry_run": True,
            "collected": 0,
            "skipped": len(offers),
            "external_pull": False,
            "reason": "dry_run",
        }

    if not offers:
        logger.info(
            "quote_collect: empty offers payload (no external supplier pull); tenant=%s",
            context.tenant_id,
        )
        return {
            "ok": True,
            "collected": 0,
            "skipped": 0,
            "status": "partial",
            "external_pull": False,
            "reason": "empty_offers_payload; pass offers[] or use live_scraper / crawler bridge",
        }

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
                "source": offer.get("source") or "payload",
            },
        )
        collected += 1
    return {
        "ok": True,
        "collected": collected,
        "skipped": skipped,
        "status": "ok" if collected else "partial",
        "external_pull": False,
        "reason": None if collected else "no_offers_applied",
    }
