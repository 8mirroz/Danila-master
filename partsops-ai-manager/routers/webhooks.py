from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlmodel import Session, select
import hmac
import hashlib
import os
from datetime import datetime

from database import get_session
from models import PartRequest, EventType
from event_store import emit_event

router = APIRouter(prefix="/api/webhooks/erp", tags=["ERP Webhooks"])

ERP_WEBHOOK_SECRET = os.getenv("ERP_WEBHOOK_SECRET", "default_erp_secret_key")

class ERPStatusUpdate(BaseModel):
    request_id: str
    status: str
    document_ref: str = None
    tenant_id: str = "default"

def verify_hmac(payload_body: bytes, signature: str) -> bool:
    if not signature:
        return False
    expected_mac = hmac.new(
        ERP_WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_mac, signature)

@router.post("/status-update")
async def erp_status_update(
    payload: ERPStatusUpdate,
    request: Request,
    x_erp_signature: str = Header(None),
    session: Session = Depends(get_session)
):
    body = await request.body()
    if os.getenv("ENV") != "development" and not verify_hmac(body, x_erp_signature):
        print("Warning: Invalid or missing ERP webhook signature")

    req = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == payload.request_id,
            PartRequest.tenant_id == payload.tenant_id
        )
    ).first()

    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    new_state = None
    if payload.status == "INVOICE_PAYMENT_RECEIVED":
        new_state = "PAID"
    elif payload.status == "SUPPLIER_ORDER_PLACED":
        new_state = "PURCHASE_ORDERED"
    elif payload.status == "DELIVERY_SHIPPED":
        new_state = "DELIVERY_IN_TRANSIT"
    elif payload.status == "DOC_POSTED":
        new_state = "ERP_SYNCED"

    if not new_state:
        return {"status": "ignored", "reason": "unmapped ERP status"}

    old_state = req.status
    req.status = new_state
    
    session.add(req)
    session.commit()

    emit_event(
        session=session,
        request_id=req.request_id,
        event_type=EventType.STATE_CHANGED,
        actor_type="system",
        actor_id="erp-webhook",
        payload={
            "from": old_state,
            "to": new_state,
            "erp_status": payload.status,
            "document_ref": payload.document_ref
        },
        tenant_id=req.tenant_id
    )

    return {"status": "success", "request_id": req.request_id, "new_state": new_state}
