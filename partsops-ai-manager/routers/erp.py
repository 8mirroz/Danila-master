from __future__ import annotations

import json
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, col, select

from database import get_session
from models import ERPSyncLog, PartRequest, RequestState
from rbac import CurrentPrincipal, get_current_principal, get_privileged_tenant
from services.request_service import RequestService
from services.service_api_keys import verify_key
from suppliers import Invoice

router = APIRouter(prefix="/api/erp", tags=["ERP"])


class ErpSyncPayload(BaseModel):
    dry_run: Optional[bool] = None


def _integration_tenant(
    x_partsops_service_key: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_session),
) -> str:
    if not x_partsops_service_key:
        raise HTTPException(401, "X-PartsOps-Service-Key is required")
    return verify_key(session, x_partsops_service_key, "erp:read").organization_id


@router.get("/integration/status/{request_id}")
def integration_erp_status(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(_integration_tenant),
):
    """Service-key-only ERP status endpoint for approved integration clients."""
    return erp_status(request_id=request_id, session=session, tenant_id=tenant_id)


@router.get("/status/{request_id}")
def erp_status(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    request = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    invoice = session.exec(
        select(Invoice)
        .where(
            Invoice.request_id == request_id,
            Invoice.tenant_id == tenant_id,
        )
        .order_by(col(Invoice.created_at).desc())
    ).first()
    sync_log = session.exec(
        select(ERPSyncLog)
        .where(
            ERPSyncLog.request_id == request_id,
            ERPSyncLog.tenant_id == tenant_id,
        )
        .order_by(col(ERPSyncLog.created_at).desc())
    ).first()
    sync_status = sync_log.status if sync_log else "NOT_SYNCED"
    dry_run = False
    if sync_log and sync_log.erp_response_json:
        try:
            dry_run = bool(json.loads(sync_log.erp_response_json).get("dry_run"))
        except (TypeError, ValueError):
            dry_run = False
    if dry_run and sync_status == "SUCCESS":
        sync_status = "DRY_RUN"
    return {
        "request_id": request_id,
        "request_status": request.status,
        "quotation_ref": request.erp_quotation_ref,
        "invoice_ref": request.erp_invoice_ref
        or (invoice.invoice_number if invoice else None),
        "sync_status": sync_status,
        "dry_run": dry_run,
        "sync_id": sync_log.sync_id if sync_log else None,
        "last_error": sync_log.last_error if sync_log else None,
        "updated_at": (sync_log.last_attempt_at or sync_log.created_at).isoformat()
        if sync_log
        else None,
    }


@router.post("/sync/{request_id}")
def sync_invoice_to_erp(
    request_id: str,
    payload: ErpSyncPayload = Body(default=ErpSyncPayload()),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
    x_idempotency_key: Optional[str] = Header(default=None),
    x_request_version: Optional[str] = Header(default=None),
):
    """Explicit ERP command; transient lifecycle states are never client targets."""
    if principal.role != "admin":
        raise HTTPException(
            status_code=403, detail="ERP synchronization requires admin role"
        )
    request = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    current_version = request.updated_at.isoformat() if request.updated_at else ""
    if x_request_version and x_request_version != current_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REQUEST_VERSION_CONFLICT",
                "current_version": current_version,
            },
        )
    invoice = session.exec(
        select(Invoice)
        .where(
            Invoice.request_id == request_id,
            Invoice.tenant_id == tenant_id,
        )
        .order_by(col(Invoice.created_at).desc())
    ).first()
    if not invoice:
        raise HTTPException(status_code=422, detail={"code": "ERP_INVOICE_REQUIRED"})
    try:
        pricing_evidence = json.loads(request.pricing_evidence_json or "{}")
    except (TypeError, ValueError):
        pricing_evidence = {}
    if not isinstance(pricing_evidence, dict) or not pricing_evidence.get(
        "approved_offer_snapshot"
    ):
        raise HTTPException(
            status_code=422, detail={"code": "ERP_OFFER_SNAPSHOT_REQUIRED"}
        )
    if request.status == RequestState.ERP_SYNCED:
        sync_log = session.exec(
            select(ERPSyncLog)
            .where(
                ERPSyncLog.request_id == request_id,
                ERPSyncLog.tenant_id == tenant_id,
            )
            .order_by(col(ERPSyncLog.created_at).desc())
        ).first()
        return {
            "request_id": request_id,
            "request_status": request.status,
            "invoice_ref": invoice.invoice_number,
            "sync": {
                "status": "ALREADY_SYNCED",
                "sync_id": sync_log.sync_id if sync_log else None,
                "idempotent": True,
            },
        }
    if request.status == RequestState.ERP_SYNCING:
        raise HTTPException(
            status_code=409, detail={"code": "ERP_SYNC_ALREADY_RUNNING"}
        )
    if request.status not in {
        RequestState.INVOICE_DRAFTED,
        RequestState.ERP_SYNC_FAILED,
    }:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_LIFECYCLE_TRANSITION",
                "request_status": request.status,
            },
        )

    # Persist the internal transition before performing I/O. A retry is then
    # recoverable rather than an invisible direct status mutation.
    RequestService.transition_state(
        session,
        request_id,
        tenant_id,
        RequestState.ERP_SYNCING,
        reason="sync_to_erp command",
        actor_id=f"operator:{principal.role}",
    )

    from erp_adapter import sync_invoice_draft

    result = sync_invoice_draft(
        request_id=request_id,
        session=session,
        tenant_id=tenant_id,
        dry_run=payload.dry_run,
        idempotency_key=x_idempotency_key,
    )
    target_state = (
        RequestState.ERP_SYNCED
        if result["status"] in {"SUCCESS", "ALREADY_SYNCED"}
        else RequestState.ERP_SYNC_FAILED
    )
    RequestService.transition_state(
        session,
        request_id,
        tenant_id,
        target_state,
        reason=f"ERP sync result: {result['status']}",
        actor_id="erp_adapter",
    )
    session.refresh(request)
    return {
        "request_id": request_id,
        "request_status": target_state,
        "invoice_ref": invoice.invoice_number,
        "sync": result,
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
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    if principal.role not in {"finance", "admin"}:
        raise HTTPException(
            status_code=403, detail="Invoice creation requires finance or admin role"
        )
    return RequestService.generate_invoice(session, request_id, tenant_id, body)
