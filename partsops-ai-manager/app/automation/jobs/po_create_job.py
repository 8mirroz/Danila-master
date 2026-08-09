"""Creates local PO drafts for accepted quotes.

Honesty policy:
- Never mark ERPSyncLog as SUCCESS without a real ERP response.
- Local drafts use status LOCAL_DRAFT and payload.local_draft_only=true.
- Actual ERP push remains erp_adapter / erp_sync_job.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType, ERPSyncLog

logger = logging.getLogger("automation.jobs.po_create")

# Free-form ERPSyncLog.status: PENDING|SUCCESS|FAILED|RETRYING|LOCAL_DRAFT
LOCAL_DRAFT_STATUS = "LOCAL_DRAFT"


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    items = context.payload.get("items") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "created": 0, "skipped": len(items), "local_draft_only": True}

    created = 0
    skipped = 0
    draft_ids: list[str] = []
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
        sync_id = f"PO-DRAFT-{uuid.uuid4().hex[:8].upper()}"
        session.add(
            ERPSyncLog(
                tenant_id=context.tenant_id,
                sync_id=sync_id,
                request_id=request_id,
                erp_document_type="PurchaseOrder",
                erp_document_name=po_id,
                idempotency_key=context.idempotency_key or uuid.uuid4().hex,
                status=LOCAL_DRAFT_STATUS,
                attempt_count=0,
                last_error="local_draft_only_not_sent_to_erp",
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
            payload={
                "document_type": "PurchaseOrder",
                "document_name": po_id,
                "local_draft_only": True,
                "erp_synced": False,
                "status": LOCAL_DRAFT_STATUS,
            },
        )
        draft_ids.append(po_id)
        created += 1
        logger.info(
            "po_create local draft only: po_id=%s request_id=%s (not sent to ERP)",
            po_id,
            request_id,
        )
    return {
        "ok": True,
        "created": created,
        "skipped": skipped,
        "local_draft_only": True,
        "erp_synced": False,
        "draft_ids": draft_ids,
        "status": LOCAL_DRAFT_STATUS,
    }
