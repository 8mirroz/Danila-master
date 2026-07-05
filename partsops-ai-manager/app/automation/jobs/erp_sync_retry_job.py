"""Retries failed ERP sync entries in accordance with idempotency keys."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType, ERPSyncLog

logger = logging.getLogger("automation.jobs.erp_sync_retry")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    sync_ids = context.payload.get("sync_ids") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "retried": 0, "skipped": len(sync_ids)}

    retried = 0
    skipped = 0
    for sync_id in sync_ids:
        log = session.exec(
            select(ERPSyncLog).where(ERPSyncLog.tenant_id == context.tenant_id)
            .where(ERPSyncLog.sync_id == sync_id)
        ).first()
        if not log or not log.request_id:
            skipped += 1
            continue
        row = session.exec(
            select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == log.request_id)
        ).first()
        if not row:
            skipped += 1
            continue
        append_request_event(
            session=session,
            request_id=log.request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.ERP_SYNC_FAILED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"sync_id": sync_id, "retry": True},
        )
        retried += 1
    return {"ok": True, "retried": retried, "skipped": skipped}
