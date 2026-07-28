from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlmodel import Session, select

from database import get_session
from rbac import get_privileged_tenant
from services.request_service import RequestService
from models import ERPSyncLog, PartRequest
from suppliers import Invoice

router = APIRouter(prefix="/api/erp", tags=["ERP"])


@router.get("/status/{request_id}")
def erp_status(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    request = session.exec(select(PartRequest).where(
        PartRequest.request_id == request_id,
        PartRequest.tenant_id == tenant_id,
    )).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    invoice = session.exec(select(Invoice).where(
        Invoice.request_id == request_id,
        Invoice.tenant_id == tenant_id,
    ).order_by(Invoice.created_at.desc())).first()
    sync_log = session.exec(select(ERPSyncLog).where(
        ERPSyncLog.request_id == request_id,
        ERPSyncLog.tenant_id == tenant_id,
    ).order_by(ERPSyncLog.created_at.desc())).first()
    return {
        "request_id": request_id,
        "request_status": request.status,
        "quotation_ref": request.erp_quotation_ref,
        "invoice_ref": request.erp_invoice_ref or (invoice.invoice_number if invoice else None),
        "sync_status": sync_log.status if sync_log else "NOT_SYNCED",
        "sync_id": sync_log.sync_id if sync_log else None,
        "last_error": sync_log.last_error if sync_log else None,
        "updated_at": (sync_log.last_attempt_at or sync_log.created_at).isoformat() if sync_log else None,
    }


@router.post("/pricing/preview/{request_id}")
def preview_pricing(
    request_id: str,
    body: Optional[dict[str, Any]] = Body(default=None),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.preview_pricing(session, request_id, tenant_id, body)


@router.post("/invoice/{request_id}")
def generate_invoice(
    request_id: str,
    body: Optional[dict[str, Any]] = Body(default=None),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.generate_invoice(session, request_id, tenant_id, body)
