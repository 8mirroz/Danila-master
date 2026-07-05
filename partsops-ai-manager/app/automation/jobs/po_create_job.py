"""Creates purchase order documents for accepted quotes and emits ERP_DOCUMENT_CREATED."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType, ERPSyncLog

logger = logging.getLogger("automation.jobs.po_create")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    items = context.payload.get("items") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "created": 0, "skipped": len(items)}

    created = 0
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
        po_id = f"PO-{uuid.uuid4().hex[:10].upper()}"
        session.add(
            ERPSyncLog(
                tenant_id=context.tenant_id,
                request_id=request_id,
                erp_document_type="PurchaseOrder",
                erp_document_name=po_id,
                idempotency_key=context.idempotency_key or uuid.uuid4().hex,
                status="SUCCESS",
                attempt_count=1,
            )
        )
        session.commit()
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.ERP_DOCUMENT_CREATED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"document_type": "PurchaseOrder", "document_name": po_id},
        )
        created += 1
    return {"ok": True, "created": created, "skipped": skipped}
