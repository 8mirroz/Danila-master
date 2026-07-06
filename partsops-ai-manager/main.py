"""
PartsOps AI Manager v3 — FastAPI Control Plane
Phase 1: Runtime Foundation
- Idempotency on POST /api/requests
- Event Store emitting on every request lifecycle
- State Machine validation on status transitions
- PII Masking before agent layer
- Margin Guard on invoice generation
- Audit Timeline endpoint
- ERP Sync Log
"""
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
load_dotenv()
from sqlmodel import Session, select
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional, List
import os
try:
    from agent_orchestrator import AgentOrchestrator, OrchestrationRequest, process_request  # type: ignore
    _AGENT_ORCHESTRATOR_AVAILABLE = True
except ImportError:
    AgentOrchestrator = None  # type: ignore
    OrchestrationRequest = None  # type: ignore
    process_request = None  # type: ignore
    _AGENT_ORCHESTRATOR_AVAILABLE = False
try:
    from base_agent import get_agent  # type: ignore
    _BASE_AGENT_AVAILABLE = True
except ImportError:
    get_agent = None  # type: ignore
    _BASE_AGENT_AVAILABLE = False
import json
import uuid
from datetime import datetime

from database import get_session, init_db, engine
from models import (
    PartRequest, RequestState, EventType,
)
from suppliers import Supplier, Invoice, seed_database, SupplierCatalogItem
from agents import process_intake_request
from matcher import match_part_from_db
from pii import mask_phone, mask_email, mask_vin, mask_name, mask_for_log, secure_pre_parse
from state_machine import validate_transition, transition as sm_transition
from event_store import emit_event, emit_state_change, get_events, verify_event_chain
from pricing import check_margin_guard, compute_price, PricingContext
from rbac import get_privileged_tenant, RoleChecker, require_privileged_access
from learning import save_manual_correction, calculate_system_accuracy
from sqlmodel import Session as SyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SyncSession(engine) as session:
        seed_result = seed_database(session)
        print(f"[SEED] {seed_result}")
    yield


app = FastAPI(
    title="PartsOps AI Manager API",
    version="3.0",
    description="Evidence-based operational control plane for auto parts supply automation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in (os.getenv("PARTSOPS_CORS_ORIGINS") or os.getenv("CORS_ALLOW_ORIGINS") or "http://localhost:5173,http://localhost:3000").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_json_field(raw_value: Optional[str], default):
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return default


def _find_request_by_tenant(session: Session, request_id: str, tenant_id: str) -> PartRequest | None:
    return session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()


def _build_pricing_context(
    req: PartRequest,
    session: Session,
    body: Optional[dict] = None,
):
    parts = _load_json_field(req.parts_json, [])
    body = body or {}

    logistics_cost = float(body.get("logistics_cost", 0.0) or 0.0)
    urgency_level = str(body.get("urgency_level", "normal") or "normal")
    target_margin_override = body.get("target_margin_override")
    if target_margin_override is None:
        target_margin_override = body.get("margin_override")

    line_items: list[dict] = []
    margin_violations: list[str] = []
    purchase_total = 0.0
    reliability_scores: list[float] = []
    item_matches: list[tuple[dict, dict]] = []

    for part in parts:
        part_name = str(part.get("name", "")).strip()
        if not part_name or part_name == "Неизвестная деталь":
            continue

        matches = match_part_from_db(part_name, session, threshold=50.0, limit=1, tenant_id=req.tenant_id)
        if not matches:
            continue

        best = matches[0]
        qty = max(1, int(part.get("quantity", 1) or 1))
        purchase_price = float(best["item"]["price"])
        purchase_total += purchase_price * qty
        reliability_scores.append(float(best["supplier"]["reliability_score"]))
        item_matches.append((part, best))

    if not item_matches:
        raise HTTPException(status_code=422, detail="Нет подходящих позиций для расчета цены")

    supplier_reliability = min(reliability_scores) if reliability_scores else 1.0
    pricing_result = compute_price(
        PricingContext(
            purchase_price=purchase_total,
            logistics_cost=logistics_cost,
            urgency_level=urgency_level,
            supplier_reliability_score=supplier_reliability,
            target_margin_override=float(target_margin_override) if target_margin_override is not None else None,
        )
    )

    for part, best in item_matches:
        qty = max(1, int(part.get("quantity", 1) or 1))
        purchase_price = float(best["item"]["price"])
        sale_price = round(purchase_price * (1 + pricing_result.margin_rate), 2)
        margin_check = check_margin_guard(purchase_price, sale_price, policy_key="default")
        if not margin_check["passed"]:
            margin_violations.append(f"{part.get('name', '')}: {margin_check['violation']}")

        line_items.append({
            "part_name": best["item"]["name"],
            "oem_number": best["item"]["oem_number"],
            "brand": best["item"]["brand"],
            "supplier": best["supplier"]["name"],
            "supplier_id": best["supplier"]["supplier_id"],
            "purchase_price": purchase_price,
            "sale_price": sale_price,
            "quantity": qty,
            "line_total": round(sale_price * qty, 2),
            "match_score": best["score"],
            "margin": margin_check["margin"],
            "margin_ok": margin_check["passed"],
        })

    if logistics_cost > 0:
        logistics_sale_price = round(logistics_cost * (1 + pricing_result.margin_rate), 2)
        line_items.append({
            "part_name": "Логистика",
            "oem_number": "",
            "brand": "",
            "supplier": "PartsOps",
            "supplier_id": "LOGISTICS",
            "purchase_price": logistics_cost,
            "sale_price": logistics_sale_price,
            "quantity": 1,
            "line_total": logistics_sale_price,
            "match_score": 100.0,
            "margin": pricing_result.margin_rate,
            "margin_ok": True,
        })

    return line_items, pricing_result, margin_violations


# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "PartsOps AI Manager Control Plane v3",
        "version": "3.0",
        "phase": "Phase 1 — Runtime Foundation",
    }


# ──────────────────────────────────────────────
# Requests — v3
# ──────────────────────────────────────────────

class RawRequestPayload(BaseModel):
    source: str
    text: str
    customer_name: str = "Unknown"
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    vehicle_vin: Optional[str] = None
    priority: str = "normal"


@app.get("/api/requests")
def get_requests(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    requests = session.exec(select(PartRequest).where(PartRequest.tenant_id == tenant_id)).all()
    return requests


@app.post("/api/requests")
def create_request(
    payload: RawRequestPayload,
    session: Session = Depends(get_session),
    x_idempotency_key: Optional[str] = Header(default=None),
    tenant_id: str = Depends(get_privileged_tenant),
):
    if x_idempotency_key:
        existing = session.exec(
            select(PartRequest).where(
                PartRequest.idempotency_key == x_idempotency_key,
                PartRequest.tenant_id == tenant_id,
            )
        ).first()
        if existing:
            emit_event(
                session,
                existing.request_id,
                EventType.IDEMPOTENCY_HIT,
                payload={"idempotency_key": x_idempotency_key},
                tenant_id=tenant_id,
            )
            return {"request": existing, "agent_trace": None, "idempotent": True}

    # 2. PII masking and Offline VIN Decoding before agent layer
    pre_parse = secure_pre_parse(payload.text)
    agent_text = pre_parse["masked_text"]
    vehicle_context = pre_parse["vehicle_context"]

    masked_phone = mask_phone(payload.customer_phone) if payload.customer_phone else None
    masked_email = mask_email(payload.customer_email) if payload.customer_email else None
    masked_vin = mask_vin(payload.vehicle_vin) if payload.vehicle_vin else None
    masked_name = mask_name(payload.customer_name) if payload.customer_name else payload.customer_name

    # 3. Run through LangGraph agent (with PII-safe input and vehicle context)
    agent_result = process_intake_request(agent_text, vehicle_context=vehicle_context)

    # 4. Create Request
    request_id = f"REQ-{str(uuid.uuid4())[:8].upper()}"
    status = RequestState.PART_EXTRACTION if agent_result["validation_status"] == "PASSED" else RequestState.NEEDS_CLARIFICATION

    # Use agent-extracted VIN if not supplied in payload
    final_vin = masked_vin or (mask_vin(agent_result["vehicle_vin"]) if agent_result.get("vehicle_vin") else None)

    new_request = PartRequest(
        request_id=request_id,
        tenant_id=tenant_id,
        idempotency_key=x_idempotency_key,
        source=payload.source,
        status=status,
        priority=payload.priority,
        customer_name=masked_name,
        customer_phone_masked=masked_phone,
        customer_email_masked=masked_email,
        vehicle_vin_masked=final_vin,
        vehicle_make=agent_result.get("vehicle_make"),
        vehicle_model=agent_result.get("vehicle_model"),
        vehicle_year=agent_result.get("vehicle_year"),
        parts_json=json.dumps(agent_result.get("extracted_parts", []), ensure_ascii=False, default=str),
        pricing_evidence_json=json.dumps(agent_result.get("pricing_evidence", {}), ensure_ascii=False, default=str) if agent_result.get("pricing_evidence") else None,
    )

    session.add(new_request)
    session.flush()

    # 5. Emit events in the same transaction
    emit_event(
        session,
        request_id,
        EventType.REQUEST_RECEIVED,
        actor_type="system",
        payload={
            "source": payload.source,
            "priority": payload.priority,
            "has_vin": bool(payload.vehicle_vin),
        },
        tenant_id=tenant_id,
        commit=False,
    )
    emit_event(
        session,
        request_id,
        EventType.PART_INTENT_EXTRACTED,
        actor_type="agent",
        actor_id="parts_extractor",
        payload={
            "parts_count": len(agent_result.get("extracted_parts", [])),
            "validation_status": agent_result["validation_status"],
        },
        tenant_id=tenant_id,
        commit=False,
    )
    emit_state_change(
        session,
        request_id,
        "NEW",
        status,
        reason=f"Agent validation: {agent_result['validation_status']}",
        tenant_id=tenant_id,
        commit=False,
    )

    session.commit()
    session.refresh(new_request)

    return {
        "request": {
            "request_id": new_request.request_id,
            "status": new_request.status,
            "priority": new_request.priority,
            "source": new_request.source,
            "customer_name": new_request.customer_name,
            "customer_phone_masked": new_request.customer_phone_masked,
            "customer_email_masked": new_request.customer_email_masked,
            "vehicle_vin_masked": new_request.vehicle_vin_masked,
            "created_at": new_request.created_at.isoformat(),
        },
        "agent_trace": agent_result,
        "idempotent": False,
    }


@app.get("/api/requests/{request_id}")
def get_request(
    request_id: str, 
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    req = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


@app.post("/api/requests/{request_id}/transition")
def transition_state(
    request_id: str,
    body: dict,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """Manually transition a request to a new state (with validation)."""
    req = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    target_state = body.get("target_state")
    reason = body.get("reason", "")

    result = validate_transition(req.status, target_state, req.model_dump(), strict_invariants=True)
    if not result["allowed"]:
        raise HTTPException(status_code=422, detail={"reason": result["reason"], "violations": result.get("violations", [])})

    old_state = req.status
    req.status = target_state
    req.updated_at = datetime.utcnow()
    session.add(req)

    emit_state_change(
        session,
        request_id,
        old_state,
        target_state,
        actor_type="user",
        actor_id=body.get("actor_id", "admin"),
        reason=reason,
        tenant_id=tenant_id,
        commit=False,
    )
    session.commit()
    session.refresh(req)

    return {"request_id": request_id, "old_state": old_state, "new_state": target_state}


# ──────────────────────────────────────────────
# Audit Timeline
# ──────────────────────────────────────────────

@app.get("/api/requests/{request_id}/events")
def get_request_events(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """Return full event timeline for a request."""
    req = _find_request_by_tenant(session, request_id, tenant_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    events = get_events(request_id, session, tenant_id=req.tenant_id)
    if not events:
        raise HTTPException(status_code=404, detail="No events found for this request")
    return {
        "request_id": request_id,
        "total_events": len(events),
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "occurred_at": e.occurred_at.isoformat(),
                "payload": json.loads(e.payload_json) if e.payload_json else {},
                "event_hash": e.event_hash[:8] + "...",
            }
            for e in events
        ],
    }


@app.get("/api/requests/{request_id}/audit")
def audit_event_chain(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """Verify the integrity of the hash chain for a request."""
    req = _find_request_by_tenant(session, request_id, tenant_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    result = verify_event_chain(request_id, session, tenant_id=req.tenant_id)
    return result


# ──────────────────────────────────────────────
# Suppliers & Catalog
# ──────────────────────────────────────────────

@app.get("/api/suppliers")
def get_suppliers(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    suppliers = session.exec(
        select(Supplier).where(Supplier.is_active == True, Supplier.tenant_id == tenant_id)
    ).all()
    return [
        {
            "supplier_id": s.supplier_id,
            "name": s.name,
            "contact_person": s.contact_person,
            "phone": s.phone,
            "email": s.email,
            "city": s.city,
            "specialization": s.specialization,
            "reliability_score": s.reliability_score,
            "avg_delivery_days": s.avg_delivery_days,
        }
        for s in suppliers
    ]


@app.get("/api/suppliers/{supplier_id}/items")
def get_supplier_catalog_items(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    items = session.exec(
        select(SupplierCatalogItem).where(
            SupplierCatalogItem.supplier_id == supplier_id,
            SupplierCatalogItem.tenant_id == tenant_id
        )
    ).all()
    return [
        {
            "catalog_id": item.catalog_id,
            "name": item.part_name,
            "oem_number": item.oem_number,
            "brand": item.brand,
            "price": item.price,
            "stock_qty": item.stock_qty,
            "delivery_days": item.delivery_days,
            "category": item.category,
        }
        for item in items
    ]


@app.get("/api/catalog/search")
def search_catalog(
    q: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    results = match_part_from_db(q, session, threshold=50.0, limit=10, tenant_id=tenant_id)
    return {"query": q, "matches": results, "total": len(results)}


class PricingPreviewPayload(BaseModel):
    logistics_cost: float = 0.0
    target_margin_override: Optional[float] = None
    urgency_level: str = "normal"


# ──────────────────────────────────────────────
# ERP / Invoices — v3 with Margin Guard
# ──────────────────────────────────────────────

@app.post("/api/erp/invoice/{request_id}")
def generate_invoice(
    request_id: str,
    body: Optional[dict] = None,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    role: str = Depends(RoleChecker(["admin", "finance", "manager"])),
):
    req = _find_request_by_tenant(session, request_id, tenant_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    from policy_engine import EvidenceGates
    chain_check = EvidenceGates.gate_event_chain_valid(request_id, session, tenant_id)
    if not chain_check["passed"]:
        raise HTTPException(
            status_code=403, 
            detail=f"Security Guard: {chain_check['reason']}"
        )

    if req.status not in {RequestState.APPROVED, RequestState.ERP_SYNCING}:
        raise HTTPException(status_code=422, detail="Invoice draft allowed only after APPROVED or ERP_SYNCING")

    line_items, pricing_result, margin_violations = _build_pricing_context(req, session, body)
    subtotal = pricing_result.subtotal_before_tax
    tax = pricing_result.tax_amount
    total = pricing_result.client_price
    invoice_number = f"INV-{str(uuid.uuid4())[:6].upper()}"

    # Update request state through the state machine, not by direct assignment.
    original_state = req.status
    req.erp_quotation_ref = req.erp_quotation_ref or f"Q-{invoice_number}"
    req.erp_invoice_ref = invoice_number
    req.margin_policy_passed = pricing_result.margin_policy_passed and len(margin_violations) == 0
    req.pricing_evidence_json = json.dumps({
        "line_items": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "margin_violations": margin_violations,
        "pricing_result": pricing_result.__dict__,
    }, ensure_ascii=False)
    if req.status == RequestState.APPROVED:
        req.status = sm_transition(req.status, RequestState.ERP_SYNCING, req.model_dump())
    elif req.status != RequestState.ERP_SYNCING:
        raise HTTPException(status_code=422, detail="Invoice draft allowed only after APPROVED or ERP_SYNCING")
    req.status = sm_transition(req.status, RequestState.INVOICE_DRAFTED, req.model_dump(), strict_invariants=True)
    req.updated_at = datetime.utcnow()
    session.add(req)

    # Create invoice record
    invoice = Invoice(
        invoice_number=invoice_number,
        tenant_id=tenant_id,
        request_id=request_id,
        supplier_id=line_items[0]["supplier_id"] if line_items else "",
        customer_name=req.customer_name or "",
        items_json=json.dumps(line_items, ensure_ascii=False),
        subtotal=subtotal,
        tax=tax,
        total=total,
        status="DRAFT",
    )
    session.add(invoice)

    # Emit events with the same transaction
    if original_state == RequestState.APPROVED:
        emit_state_change(
            session,
            request_id,
            RequestState.APPROVED,
            RequestState.ERP_SYNCING,
            actor_type="system",
            actor_id="invoice_builder",
            reason="Invoice builder prepared ERP sync payload",
            tenant_id=tenant_id,
            commit=False,
        )
    emit_state_change(
        session,
        request_id,
        RequestState.ERP_SYNCING,
        RequestState.INVOICE_DRAFTED,
        actor_type="system",
        actor_id="invoice_builder",
        reason="Invoice draft persisted",
        tenant_id=tenant_id,
        commit=False,
    )
    emit_event(
        session,
        request_id,
        EventType.ERP_DOCUMENT_CREATED,
        payload={
            "invoice_number": invoice_number,
            "total": total,
            "margin_policy_passed": req.margin_policy_passed,
            "margin_violations": margin_violations,
        },
        tenant_id=tenant_id,
        commit=False,
    )
    session.commit()
    session.refresh(req)

    return {
        "status": "DRAFT_CREATED",
        "invoice_number": invoice_number,
        "invoice": {
            "customer_name": req.customer_name,
            "items": line_items,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
        },
        "margin_policy_passed": req.margin_policy_passed,
        "margin_violations": margin_violations,
        "erp_link": f"http://erpnext.local/app/sales-invoice/{invoice_number}",
        "request_id": request_id,
    }


@app.get("/api/invoices")
def get_invoices(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    invoices = session.exec(select(Invoice).where(Invoice.tenant_id == tenant_id)).all()
    return [
        {
            "invoice_id": invoice.invoice_number,
            "request_id": invoice.request_id,
            "customer_name": invoice.customer_name,
            "total_price": invoice.total,
            "created_at": invoice.created_at.isoformat(),
            "status": invoice.status,
        }
        for invoice in invoices
    ]


# ──────────────────────────────────────────────
# ERP Sync & Webhooks (Phase 4)
# ──────────────────────────────────────────────

@app.post("/api/erp/sync/{request_id}")
def manual_erp_sync(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    role: str = Depends(RoleChecker(["admin", "finance", "manager"])),
):
    """Manually trigger invoice draft synchronization to ERPNext."""
    from erp_adapter import sync_invoice_draft
    result = sync_invoice_draft(request_id, session, tenant_id=tenant_id)
    if result["status"] == "ERROR":
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@app.post("/api/erp/webhook")
async def erp_webhook(
    request: Request,
    session: Session = Depends(get_session),
    x_signature_sha256: Optional[str] = Header(default=None),
):
    """Incoming webhook from ERPNext with HMAC-SHA256 verification."""
    from erp_adapter import verify_webhook_signature, process_payment_webhook
    
    body_bytes = await request.body()
    if not x_signature_sha256 or not verify_webhook_signature(body_bytes, x_signature_sha256):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    result = process_payment_webhook(payload, session)
    if result["status"] == "ERROR":
        raise HTTPException(status_code=400, detail=result["reason"])
        
    return result


@app.get("/api/erp/outbox")
def get_erp_outbox(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    role: str = Depends(RoleChecker(["admin", "finance"])),
):
    """Get pending, retrying, and DLQ entries from the ERP sync log."""
    from erp_adapter import get_pending_outbox, get_dlq_entries
    from models import ERPSyncLog
    
    pending = get_pending_outbox(session, tenant_id=tenant_id)
    dlq = get_dlq_entries(session, tenant_id=tenant_id)
    
    # Also fetch recent successes
    successes = session.exec(
        select(ERPSyncLog).where(
            ERPSyncLog.tenant_id == tenant_id,
            ERPSyncLog.status == "SUCCESS"
        ).order_by(ERPSyncLog.succeeded_at.desc()).limit(20)
    ).all()
    
    return {
        "pending": pending,
        "dlq": dlq,
        "recent_successes": successes,
    }


@app.post("/api/erp/outbox/process")
def process_pending_outbox(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    role: str = Depends(RoleChecker(["admin", "finance"])),
):
    """Manually trigger processing of all pending outbox entries."""
    from erp_adapter import get_pending_outbox, retry_sync_entry
    
    pending = get_pending_outbox(session, tenant_id=tenant_id)
    processed = []
    
    for entry in pending:
        res = retry_sync_entry(entry, session)
        processed.append(res)
        
    return {"processed_count": len(processed), "results": processed}


@app.post("/api/pricing/preview/{request_id}")
def preview_pricing(
    request_id: str,
    body: PricingPreviewPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    req = _find_request_by_tenant(session, request_id, tenant_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    line_items, pricing_result, margin_violations = _build_pricing_context(req, session, body.model_dump())
    return {
        "request_id": request_id,
        "line_items": line_items,
        "pricing": {
            "purchase_price": pricing_result.purchase_price,
            "logistics_cost": pricing_result.logistics_cost,
            "risk_buffer": pricing_result.risk_buffer,
            "urgency_buffer": pricing_result.urgency_buffer,
            "margin_amount": pricing_result.margin_amount,
            "margin_rate": pricing_result.margin_rate,
            "subtotal_before_tax": pricing_result.subtotal_before_tax,
            "tax_amount": pricing_result.tax_amount,
            "client_price": pricing_result.client_price,
            "policy_min_margin": pricing_result.policy_min_margin,
            "margin_policy_passed": pricing_result.margin_policy_passed and len(margin_violations) == 0,
            "price_anomaly_detected": pricing_result.price_anomaly_detected,
            "price_deviation": pricing_result.price_deviation,
            "auto_approve_allowed": pricing_result.auto_approve_allowed,
            "violations": pricing_result.violations,
            "warnings": pricing_result.warnings,
            "margin_violations": margin_violations,
        },
    }


@app.get("/api/admin/llm-status")
def llm_provider_status(_: bool = Depends(require_privileged_access)):
    """Return status of all configured LLM providers (for ops/admin panel)."""
    from llm import get_provider_status, reload_providers
    return {"providers": get_provider_status()}


@app.post("/api/admin/llm-reload")
def reload_llm_providers(_: bool = Depends(require_privileged_access)) -> dict:
    """Hot-reload LLM provider config from env vars."""
    from llm import reload_providers, get_provider_status
    reload_providers()
    return {"status": "reloaded", "providers": get_provider_status()}


@app.get("/api/admin/budget-stats")
def budget_stats(_: bool = Depends(require_privileged_access)):
    """Return current LLM budget statistics (hourly tokens, daily cost)."""
    from budget_guard import budget_guard
    return budget_guard.get_usage_stats()


# ──────────────────────────────────────────────
# OpenAI-Compatible Streaming Chat Completions
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "default"
    messages: List[ChatMessage]
    temperature: float = 0.2
    stream: bool = True
    priority: str = "normal"

@app.post("/api/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    OpenAI-compatible streaming chat completions endpoint.
    
    Supports:
    - model aliases: "default", "fast", "reasoning"
    - streaming (SSE) and non-streaming modes
    - priority routing (normal/urgent/vip → model selection)
    - BudgetGuard enforcement
    - Multi-provider fallback with retry
    
    Returns SSE stream in OpenAI format or JSON for non-streaming.
    """
    from llm import call_llm_stream, call_llm_async, resolve_model, PROVIDERS

    # Extract the last user message as the prompt
    user_messages = [m for m in req.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="At least one user message required")

    user_prompt = user_messages[-1].content

    # Build system prompt from system messages
    system_msgs = [m.content for m in req.messages if m.role == "system"]
    system_prompt = system_msgs[0] if system_msgs else "You are an AI assistant for automotive parts supply chain."

    if not req.stream:
        # Non-streaming: use async call and wrap in OpenAI response format
        import time as _time
        content = await call_llm_async(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=req.model,
            temperature=req.temperature,
            priority=req.priority,
        )
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(_time.time()),
            "model": req.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    # Streaming: SSE
    async def generate_sse():
        async for chunk in call_llm_stream(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=req.model,
            temperature=req.temperature,
            priority=req.priority,
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx: disable buffering
        },
    )


# ──────────────────────────────────────────────
# Intelligence Layer (Phase 4)
# ──────────────────────────────────────────────

class ReturnRiskQuery(BaseModel):
    part_name: str
    brand: str = ""

class PriceMedianQuery(BaseModel):
    catalog_id: str

class PriceUpdatePayload(BaseModel):
    catalog_id: str
    price: float
    currency: str = "RUB"

class SupplierReliabilityUpdate(BaseModel):
    supplier_id: str
    new_score: float
    event_type: str
    reason: str

@app.get("/api/intelligence/price-median/{catalog_id}")
def get_price_median(catalog_id: str, session: Session = Depends(get_session)):
    """Get 90-day median price for a catalog item."""
    from intelligence import get_90d_median_price
    median = get_90d_median_price(catalog_id, session)
    return {"catalog_id": catalog_id, "median_price_90d": median}

@app.post("/api/intelligence/price-update")
def record_price(payload: PriceUpdatePayload, session: Session = Depends(get_session)):
    """Append a new price entry to the PriceHistoryLedger."""
    from intelligence import record_price_update
    record_price_update(payload.catalog_id, payload.price, payload.currency, session)
    return {"status": "recorded", "catalog_id": payload.catalog_id, "price": payload.price, "currency": payload.currency}

@app.get("/api/intelligence/supplier-reliability/{supplier_id}")
def get_supplier_reliability(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """Return the reliability history for a supplier."""
    from models import SupplierReliabilityLog
    from sqlmodel import select
    logs = session.exec(
        select(SupplierReliabilityLog).where(
            SupplierReliabilityLog.supplier_id == supplier_id,
            SupplierReliabilityLog.tenant_id == tenant_id,
        ).order_by(SupplierReliabilityLog.logged_at.desc())
    ).all()
    return {
        "supplier_id": supplier_id,
        "current_score": logs[0].reliability_score if logs else None,
        "history": [
            {
                "score": l.reliability_score,
                "event_type": l.event_type,
                "reason": l.reason,
                "logged_at": l.logged_at.isoformat(),
            }
            for l in logs
        ],
    }

@app.post("/api/intelligence/supplier-reliability")
def update_supplier_reliability_endpoint(
    payload: SupplierReliabilityUpdate,
    session: Session = Depends(get_session),
    role: str = Depends(RoleChecker(["admin", "manager"])),
):
    """Update supplier reliability score with audit log."""
    from intelligence import update_supplier_reliability
    update_supplier_reliability(
        payload.supplier_id, payload.new_score, payload.event_type, payload.reason, session
    )
    return {"status": "updated", "supplier_id": payload.supplier_id}

@app.post("/api/intelligence/assess-return-risk")
def assess_return_risk_endpoint(payload: ReturnRiskQuery):
    """Assess warranty/return risk for a part."""
    from intelligence import assess_return_risk
    return assess_return_risk(payload.part_name, payload.brand)

@app.get("/api/intelligence/po-drafts/{request_id}")
def get_po_drafts(request_id: str, session: Session = Depends(get_session)):
    """Generate draft purchase orders grouped by supplier for a request."""
    from intelligence import generate_purchase_order_drafts
    drafts = generate_purchase_order_drafts(request_id, session)
    return {"request_id": request_id, "po_drafts": drafts}

# ──────────────────────────────────────────────
# Agent Orchestrator (Phase 6)
# ──────────────────────────────────────────────

from agent_orchestrator import AgentOrchestrator, OrchestrationRequest
orchestrator = AgentOrchestrator()

@app.post("/api/orchestrate")
def orchestrate_request(req: OrchestrationRequest):
    """Run full agent orchestration pipeline on a raw request string."""
    result = orchestrator.run(req)
    return result

class QuickOrchestratePayload(BaseModel):
    raw_request: str
    customer_name: str = "Unknown"
    priority: str = "normal"

@app.post("/api/orchestrate/quick")
def quick_orchestrate(body: QuickOrchestratePayload):
    """Quick orchestration call without full payload."""
    from agent_orchestrator import process_request
    return process_request(body.raw_request, body.customer_name, body.priority)

# ──────────────────────────────────────────────
# Supervisor Agent — Copilot (Phase 6)
# ──────────────────────────────────────────────

from base_agent import get_agent

@app.get("/api/copilot/{request_id}")
def get_copilot_instruction(request_id: str, session: Session = Depends(get_session)):
    """Get operator copilot instructions for a request based on current state."""
    copilot = get_agent("operator_copilot")
    if not copilot:
        raise HTTPException(status_code=500, detail="Copilot agent not registered")

    req = session.exec(
        select(PartRequest).where(PartRequest.request_id == request_id)
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    ctx: AgentContext = {
        "request_id": request_id,
        "validation_status": req.validation_status or "PENDING",
        "priority": req.priority,
        "trace": [],
    }
    result = copilot.run(ctx)
    return result

# ──────────────────────────────────────────────
# Budget Guard — Config & Check endpoints
# ──────────────────────────────────────────────

from budget_guard import BudgetConfig, budget_guard

@app.post("/api/admin/budget/config")
def set_budget_config(config: BudgetConfig, _: bool = Depends(require_privileged_access)):
    """Register or update a budget configuration for a model."""
    budget_guard.register_config(config)
    return {"status": "registered", "model": config.model_name}

class BudgetCheckQuery(BaseModel):
    model: str
    tokens: int = 5000

@app.post("/api/admin/budget/check")
def check_budget(query: BudgetCheckQuery, _: bool = Depends(require_privileged_access)):
    """Check if a model/token budget would pass."""
    result = budget_guard.check_budget(query.model, query.tokens)
    return result


# ──────────────────────────────────────────────
# State Machine info
# ──────────────────────────────────────────────

@app.get("/api/state-machine/{state}")
def get_allowed_transitions(state: str):
    """Return allowed next states for a given state."""
    from state_machine import get_allowed_next, is_terminal
    return {
        "current_state": state,
        "allowed_next": get_allowed_next(state),
        "is_terminal": is_terminal(state),
    }


# ──────────────────────────────────────────────
# Learning Loop (Phase 5)
# ──────────────────────────────────────────────

class ManualCorrectionPayload(BaseModel):
    source_text: str
    corrected_parts_json: str
    correction_reason_tags: list[str]
    corrected_vehicle_json: Optional[str] = None

@app.post("/api/requests/{request_id}/correction")
def submit_manual_correction(
    request_id: str,
    payload: ManualCorrectionPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    role: str = Depends(RoleChecker(["admin", "manager"])),
):
    """Save manual correction to Golden Dataset."""
    req = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id
        )
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    sample = save_manual_correction(
        session=session,
        request_id=request_id,
        tenant_id=tenant_id,
        source_text=payload.source_text,
        corrected_parts_json=payload.corrected_parts_json,
        correction_reason_tags=payload.correction_reason_tags,
        user_id="admin_user", # in real app from JWT
        corrected_vehicle_json=payload.corrected_vehicle_json,
    )
    return {"status": "SUCCESS", "sample_id": sample.sample_id}


@app.get("/api/analytics/accuracy")
def get_accuracy_metrics(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    role: str = Depends(RoleChecker(["admin", "finance"])),
):
    """Get system accuracy metric and top correction reasons."""
    return calculate_system_accuracy(session, tenant_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
