"""Syncs outbound ERP documents with upstream financial/warehouse status."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType, ERPSyncLog

logger = logging.getLogger("automation.jobs.erp_sync")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    logs = context.payload.get("sync_logs") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "synced": 0, "skipped": len(logs)}

    synced = 0
    skipped = 0
    for item in logs:
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
            event_type=EventType.PAYMENT_STATUS_SYNCED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"status": item.get("erp_status", "unknown"), "attempt": item.get("attempt", 1)},
        )
        synced += 1
    return {"ok": True, "synced": synced, "skipped": skipped}
