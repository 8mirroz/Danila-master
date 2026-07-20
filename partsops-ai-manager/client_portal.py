"""
Client Portal MVP (Phase 9) — public tracking, offer acceptance.
"""
from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlmodel import Session, select
from models import PartRequest, RequestState
from state_machine import validate_transition, transition
from event_store import append_request_event
from rbac import get_current_tenant

TRACKING_TOKEN_TTL_HOURS = 72

def generate_tracking_token(request_id: str) -> str:
    """Generate cryptographically secure token: SHA256(request_id + salt)."""
    salt = secrets.token_hex(16)
    token = hashlib.sha256(f"{request_id}:{salt}".encode()).hexdigest()
    return token

def create_tracking_token(request_id: str, tenant_id: str, expires_hours: int = 72) -> str:
    """Generate and store tracking token in the database."""
    from database import engine
    from sqlmodel import Session, select
    from models import PartRequest
    
    token = generate_tracking_token(request_id)
    
    with Session(engine) as session:
        req = session.exec(
            select(PartRequest).where(
                PartRequest.request_id == request_id,
                PartRequest.tenant_id == tenant_id
            )
        ).first()
        
        if req:
            req.tracking_token = token
            req.tracking_token_expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            session.add(req)
            session.commit()
    
    return token

def verify_tracking_token(token: str, request_id: str) -> bool:
    """Verify token matches request_id (token never stored, verified by re-hashing)."""
    # In production, compare against stored token in DB
    return False  # Placeholder — actual verification uses DB lookup

def get_public_request_view(token: str, session: Session, tenant_id: str) -> Optional[Dict[str, Any]]:
    """Return public view of request (no purchase price, margin, supplier_id)."""
    from models import PartRequest
    stmt = select(PartRequest).where(PartRequest.tracking_token == token)
    req = session.exec(stmt).first()
    if not req:
        return None
    
    # Ensure tenant-scoped (prevent token collision across tenants)
    if req.tenant_id != tenant_id:
        return None
    
    # Mask sensitive data for public view
    try:
        parts = []
        if req.parts_json:
            import json
            parts_data = json.loads(req.parts_json)
            for p in parts_data:
                parts.append({
                    "name": p.get("name"),
                    "quantity": p.get("quantity"),
                    "sale_price": p.get("sale_price"),
                    "match_score": p.get("match_score")
                })
        
        return {
            "request_id": req.request_id,
            "status": req.status,
            "customer_name": req.customer_name,
            "vehicle_make": req.vehicle_make,
            "vehicle_model": req.vehicle_model,
            "vehicle_year": req.vehicle_year,
            "parts": parts,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "updated_at": req.updated_at.isoformat() if req.updated_at else None,
            "erp_quotation_ref": req.erp_quotation_ref,
            "erp_invoice_ref": req.erp_invoice_ref,
            "tracking_token": req.tracking_token
        }
    except Exception:
        return None

def accept_offer(token: str, session: Session, tenant_id: str) -> Dict[str, Any]:
    """Transition SENT_TO_CLIENT → PAID via state machine + event."""
    from models import PartRequest, RequestEvent, EventType
    stmt = select(PartRequest).where(PartRequest.tracking_token == token)
    req = session.exec(stmt).first()
    if not req or req.tenant_id != tenant_id:
        return {"ok": False, "error": "Request not found"}
    
    if req.status != RequestState.SENT_TO_CLIENT:
        return {"ok": False, "error": f"Cannot accept: current status is {req.status}"}
    
    # Validate transition
    validation = validate_transition(req.status, RequestState.PAID, req.model_dump())
    if not validation["allowed"]:
        return {"ok": False, "error": validation["reason"]}
    
    # Perform transition
    new_state = transition(req.status, RequestState.PAID, req.model_dump())
    req.status = new_state
    
    # Emit event
    append_request_event(
        session=session,
        request_id=req.request_id,
        tenant_id=tenant_id,
        event_type=EventType.STATE_CHANGED,
        actor_type="client",
        actor_id="public_portal",
        payload={"from": req.status, "to": new_state, "reason": "Offer accepted by client"}
    )
    
    session.add(req)
    session.commit()
    return {"ok": True, "new_status": new_state}

def reject_offer(token: str, reason: str, session: Session, tenant_id: str) -> Dict[str, Any]:
    """Transition SENT_TO_CLIENT → CLIENT_REJECTED."""
    from models import PartRequest, RequestEvent, EventType
    stmt = select(PartRequest).where(PartRequest.tracking_token == token)
    req = session.exec(stmt).first()
    if not req or req.tenant_id != tenant_id:
        return {"ok": False, "error": "Request not found"}
    
    if req.status != RequestState.SENT_TO_CLIENT:
        return {"ok": False, "error": f"Cannot reject: current status is {req.status}"}
    
    old_status = req.status
    new_state = transition(req.status, RequestState.CLIENT_REJECTED, req.model_dump())
    req.status = new_state
    
    append_request_event(
        session=session,
        request_id=req.request_id,
        tenant_id=tenant_id,
        event_type=EventType.STATE_CHANGED,
        actor_type="client",
        actor_id="public_portal",
        payload={"from": old_status, "to": new_state, "reason": f"Offer rejected: {reason}"}
    )
    
    session.add(req)
    session.commit()
    return {"ok": True, "new_status": new_state}