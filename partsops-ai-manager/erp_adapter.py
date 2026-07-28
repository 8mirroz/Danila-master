"""
PartsOps AI Manager v3 — ERPNext Outbox Adapter.

Implements:
- Transactional Outbox pattern for ERP synchronization.
- HMAC-SHA256 webhook signature verification.
- Idempotent payment webhook processing.
- Retry with exponential backoff + DLQ (Dead Letter Queue).
- Dry-run mode (default when ERPNEXT_URL is not set).

Models used: ERPSyncLog, OutboundMessage, Invoice (from suppliers.py).
State transitions: INVOICE_DRAFTED → SENT_TO_CLIENT → PAID (via state_machine).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from models import (
    ERPSyncLog,
    EventType,
    OutboundMessage,
    PartRequest,
    RequestState,
)
from suppliers import Invoice
from state_machine import transition as sm_transition, StateMachineError
from event_store import emit_event, emit_state_change


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

ERPNEXT_URL = os.getenv("ERPNEXT_URL", "")
ERPNEXT_API_KEY = os.getenv("ERPNEXT_API_KEY", "")
ERPNEXT_API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")
PARTSOPS_ENV = os.getenv("PARTSOPS_ENV", "dev").strip().lower()
def _load_webhook_secret() -> str:
    secret = os.getenv("ERP_WEBHOOK_SECRET")
    if secret:
        return secret
    generated = os.urandom(32).hex()
    import warnings
    warnings.warn(
        "ERP_WEBHOOK_SECRET is not set. Generated a one-time secret for this process. "
        "Set ERP_WEBHOOK_SECRET env var to a persistent value in production.",
        RuntimeWarning,
    )
    return generated

ERP_WEBHOOK_SECRET = _load_webhook_secret()
# Dry-run is a test/development capability only.  A production process must
# report an unavailable ERP as blocked/failed instead of manufacturing a sync.
ERP_DRY_RUN = PARTSOPS_ENV not in {"prod", "production"} and os.getenv("ERP_DRY_RUN", "1") == "1"

MAX_RETRY_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MULTIPLIER = 4.0


# ──────────────────────────────────────────────
# HMAC-SHA256 Webhook Signature Verification
# ──────────────────────────────────────────────

def verify_webhook_signature(payload_bytes: bytes, signature_header: str, secret: Optional[str] = None) -> bool:
    """
    Verify HMAC-SHA256 signature of incoming webhook payload.
    
    Args:
        payload_bytes: Raw request body bytes.
        signature_header: Value of x-signature-sha256 header.
        secret: HMAC secret key (defaults to ERP_WEBHOOK_SECRET env var).
    
    Returns:
        True if signature is valid, False otherwise.
    """
    secret = secret or ERP_WEBHOOK_SECRET
    if not signature_header or not secret:
        return False
    
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature_header)


def compute_webhook_signature(payload_bytes: bytes, secret: Optional[str] = None) -> str:
    """Compute HMAC-SHA256 signature for testing/sending webhooks."""
    secret = secret or ERP_WEBHOOK_SECRET
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


# ──────────────────────────────────────────────
# ERP Sync — Invoice Draft
# ──────────────────────────────────────────────

def sync_invoice_draft(
    request_id: str,
    session: Session,
    tenant_id: str = "default",
    dry_run: Optional[bool] = None,
) -> dict:
    """
    Synchronize an invoice draft to ERPNext via Transactional Outbox.
    
    Steps:
    1. Find the invoice for this request.
    2. Create ERPSyncLog entry (PENDING).
    3. Attempt HTTP POST to ERPNext (or dry-run).
    4. Update ERPSyncLog status.
    5. Emit ERP sync event.
    
    Args:
        request_id: The request ID to sync.
        session: SQLModel session (same transaction).
        tenant_id: Tenant scope.
        dry_run: Override dry-run mode. None = use env default.
    
    Returns:
        dict with sync result.
    """
    if dry_run is None:
        dry_run = ERP_DRY_RUN
    if PARTSOPS_ENV in {"prod", "production"}:
        dry_run = False
    
    # Find invoice
    invoice = session.exec(
        select(Invoice).where(
            Invoice.request_id == request_id,
            Invoice.tenant_id == tenant_id,
        )
    ).first()
    
    if not invoice:
        return {
            "status": "ERROR",
            "reason": f"No invoice found for request {request_id}",
        }
    
    # Idempotency: check if already synced
    idempotency_key = f"erp-sync-invoice-{invoice.invoice_number}"
    existing_sync = session.exec(
        select(ERPSyncLog).where(
            ERPSyncLog.idempotency_key == idempotency_key,
            ERPSyncLog.tenant_id == tenant_id,
        )
    ).first()
    
    if existing_sync and existing_sync.status == "SUCCESS":
        return {
            "status": "ALREADY_SYNCED",
            "sync_id": existing_sync.sync_id,
            "erp_document_name": existing_sync.erp_document_name,
        }
    
    # Create or update sync log entry
    if existing_sync:
        sync_log = existing_sync
    else:
        sync_log = ERPSyncLog(
            sync_id=f"SYNC-{uuid.uuid4().hex[:8].upper()}",
            tenant_id=tenant_id,
            request_id=request_id,
            erp_document_type="SalesInvoice",
            idempotency_key=idempotency_key,
            status="PENDING",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(sync_log)
        session.flush()
    
    # Build ERP payload
    items_data = json.loads(invoice.items_json) if invoice.items_json else []
    erp_payload = {
        "doctype": "Sales Invoice",
        "customer": invoice.customer_name,
        "posting_date": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d"),
        "due_date": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d"),
        "currency": "RUB",
        "items": [
            {
                "item_code": item.get("oem_number", "GENERIC"),
                "item_name": item.get("part_name", ""),
                "qty": item.get("quantity", 1),
                "rate": item.get("sale_price", 0),
                "amount": item.get("line_total", 0),
            }
            for item in items_data
        ],
        "taxes": [
            {
                "charge_type": "On Net Total",
                "account_head": "VAT - PC",
                "rate": 20.0,
            }
        ],
        "custom_partsops_request_id": request_id,
        "custom_partsops_invoice_ref": invoice.invoice_number,
    }
    
    # Attempt sync
    result = _attempt_erp_sync(sync_log, erp_payload, dry_run)
    
    # Update sync log
    sync_log.last_attempt_at = datetime.now(timezone.utc).replace(tzinfo=None)
    sync_log.attempt_count += 1
    
    if result["success"]:
        sync_log.status = "SUCCESS"
        sync_log.erp_document_name = result.get("erp_document_name", f"DRY-{invoice.invoice_number}")
        sync_log.erp_response_json = json.dumps(result, ensure_ascii=False)
        sync_log.succeeded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        if sync_log.attempt_count >= MAX_RETRY_ATTEMPTS:
            sync_log.status = "DLQ"
        else:
            sync_log.status = "RETRYING"
        sync_log.last_error = result.get("error", "Unknown error")
        sync_log.erp_response_json = json.dumps(result, ensure_ascii=False)
    
    session.add(sync_log)
    
    # Emit event
    emit_event(
        session,
        request_id,
        EventType.ERP_DOCUMENT_CREATED if result["success"] else EventType.ERP_SYNC_FAILED,
        actor_type="system",
        actor_id="erp_adapter",
        payload={
            "sync_id": sync_log.sync_id,
            "status": sync_log.status,
            "attempt": sync_log.attempt_count,
            "dry_run": dry_run,
            "erp_document_name": sync_log.erp_document_name,
        },
        tenant_id=tenant_id,
        commit=False,
    )
    
    session.commit()
    
    return {
        "status": sync_log.status,
        "sync_id": sync_log.sync_id,
        "erp_document_name": sync_log.erp_document_name,
        "attempt": sync_log.attempt_count,
        "dry_run": dry_run,
    }


def _attempt_erp_sync(sync_log: ERPSyncLog, erp_payload: dict, dry_run: bool) -> dict:
    """
    Attempt to sync with ERPNext. Returns dict with success/error.
    In dry-run mode, simulates a successful sync.
    """
    if dry_run:
        return {
            "success": True,
            "erp_document_name": f"DRY-SINV-{uuid.uuid4().hex[:6].upper()}",
            "dry_run": True,
            "message": "Dry-run: no actual HTTP request sent",
        }
    
    # Real HTTP sync
    try:
        import httpx
        
        headers = {
            "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
            "Content-Type": "application/json",
        }
        
        response = httpx.post(
            f"{ERPNEXT_URL}/api/resource/Sales Invoice",
            headers=headers,
            json={"data": erp_payload},
            timeout=30.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )
        
        if response.status_code in (200, 201):
            data = response.json()
            return {
                "success": True,
                "erp_document_name": data.get("data", {}).get("name", "UNKNOWN"),
                "dry_run": False,
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:500]}",
                "dry_run": False,
            }
    except ImportError:
        return {
            "success": False,
            "error": "httpx not installed. Install with: pip install httpx",
            "dry_run": False,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Connection error: {str(e)[:500]}",
            "dry_run": False,
        }


# ──────────────────────────────────────────────
# Payment Webhook Processing
# ──────────────────────────────────────────────

def process_payment_webhook(
    payload: dict,
    session: Session,
    tenant_id: str = "default",
) -> dict:
    """
    Process an incoming payment webhook from ERPNext.
    
    Webhook payload expected:
    {
        "event": "payment_received",
        "invoice_number": "INV-XXXXXX",
        "payment_ref": "PAY-XXXXXX",
        "amount": 12345.00,
        "currency": "RUB",
        "paid_at": "2026-07-05T12:00:00"
    }
    
    Idempotent: duplicate webhooks with the same invoice_number are ignored.
    """
    event_type = payload.get("event", "")
    invoice_number = payload.get("invoice_number", "")
    payment_ref = payload.get("payment_ref", "")
    
    if event_type != "payment_received":
        return {"status": "IGNORED", "reason": f"Unknown event type: {event_type}"}
    
    if not invoice_number:
        return {"status": "ERROR", "reason": "Missing invoice_number in webhook payload"}
    
    # Idempotency: check if already processed
    idempotency_key = f"webhook-payment-{invoice_number}"
    existing = session.exec(
        select(ERPSyncLog).where(
            ERPSyncLog.idempotency_key == idempotency_key,
            ERPSyncLog.tenant_id == tenant_id,
        )
    ).first()
    
    if existing:
        return {
            "status": "DUPLICATE",
            "sync_id": existing.sync_id,
            "message": "Payment webhook already processed",
        }
    
    # Find invoice and request
    invoice = session.exec(
        select(Invoice).where(
            Invoice.invoice_number == invoice_number,
            Invoice.tenant_id == tenant_id,
        )
    ).first()
    
    if not invoice:
        return {"status": "ERROR", "reason": f"Invoice {invoice_number} not found"}
    
    # Validate payment amount against invoice total
    try:
        webhook_amount = float(payload.get("amount", 0))
    except (TypeError, ValueError):
        webhook_amount = 0.0
    invoice_total = float(invoice.total or 0)
    if webhook_amount <= 0:
        return {"status": "ERROR", "reason": "Invalid payment amount in webhook payload"}
    if abs(webhook_amount - invoice_total) > 0.01 and webhook_amount < invoice_total:
        return {
            "status": "ERROR",
            "reason": f"Payment amount {webhook_amount} does not match invoice total {invoice_total}",
        }
    
    request = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == invoice.request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()
    
    if not request:
        return {"status": "ERROR", "reason": f"Request for invoice {invoice_number} not found"}
    
    # Create sync log for the payment webhook
    sync_log = ERPSyncLog(
        sync_id=f"SYNC-{uuid.uuid4().hex[:8].upper()}",
        tenant_id=tenant_id,
        request_id=invoice.request_id,
        erp_document_type="PaymentEntry",
        erp_document_name=payment_ref,
        idempotency_key=idempotency_key,
        status="SUCCESS",
        attempt_count=1,
        erp_response_json=json.dumps(payload, ensure_ascii=False),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        last_attempt_at=datetime.now(timezone.utc).replace(tzinfo=None),
        succeeded_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(sync_log)
    
    # Update invoice status
    invoice.status = "PAID"
    session.add(invoice)
    
    # Update request: set payment ref and transition state
    request.erp_payment_ref = payment_ref
    old_state = request.status
    
    # Only transition if in a valid source state
    try:
        if old_state == RequestState.SENT_TO_CLIENT:
            new_state = sm_transition(old_state, RequestState.PAID, request.model_dump())
            request.status = new_state
        elif old_state == RequestState.INVOICE_DRAFTED:
            # Must go through SENT_TO_CLIENT first
            intermediate = sm_transition(old_state, RequestState.SENT_TO_CLIENT, request.model_dump())
            request.status = intermediate
            new_state = sm_transition(intermediate, RequestState.PAID, request.model_dump())
            request.status = new_state
        else:
            # Already in a later state or incompatible — just record the payment
            new_state = old_state
    except StateMachineError:
        new_state = old_state
    
    request.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(request)
    
    # Emit events
    emit_event(
        session,
        invoice.request_id,
        EventType.PAYMENT_STATUS_SYNCED,
        actor_type="external",
        actor_id="erpnext_webhook",
        payload={
            "invoice_number": invoice_number,
            "payment_ref": payment_ref,
            "amount": payload.get("amount"),
            "old_state": old_state,
            "new_state": new_state,
        },
        tenant_id=tenant_id,
        commit=False,
    )
    
    if old_state != new_state:
        emit_state_change(
            session,
            invoice.request_id,
            old_state,
            new_state,
            actor_type="external",
            actor_id="erpnext_webhook",
            reason=f"Payment received: {payment_ref}",
            tenant_id=tenant_id,
            commit=False,
        )
    
    session.commit()
    
    return {
        "status": "PROCESSED",
        "sync_id": sync_log.sync_id,
        "request_id": invoice.request_id,
        "old_state": old_state,
        "new_state": new_state,
        "payment_ref": payment_ref,
    }


# ──────────────────────────────────────────────
# Outbox Processor (batch retry)
# ──────────────────────────────────────────────

def get_pending_outbox(session: Session, tenant_id: str = "default", limit: int = 50) -> list[ERPSyncLog]:
    """Get pending/retrying ERP sync entries for processing."""
    return session.exec(
        select(ERPSyncLog).where(
            ERPSyncLog.tenant_id == tenant_id,
            ERPSyncLog.status.in_(["PENDING", "RETRYING"]),
        ).order_by(ERPSyncLog.created_at.asc()).limit(limit)
    ).all()


def get_dlq_entries(session: Session, tenant_id: str = "default") -> list[ERPSyncLog]:
    """Get dead-letter queue entries (failed after all retries)."""
    return session.exec(
        select(ERPSyncLog).where(
            ERPSyncLog.tenant_id == tenant_id,
            ERPSyncLog.status == "DLQ",
        ).order_by(ERPSyncLog.created_at.asc())
    ).all()


def retry_sync_entry(
    sync_log: ERPSyncLog,
    session: Session,
    dry_run: Optional[bool] = None,
) -> dict:
    """
    Retry a single ERPSyncLog entry with exponential backoff.
    
    Backoff: attempt 1 → 1s, attempt 2 → 4s, attempt 3 → 16s.
    After MAX_RETRY_ATTEMPTS, entry goes to DLQ.
    """
    if dry_run is None:
        dry_run = ERP_DRY_RUN
    
    if sync_log.attempt_count >= MAX_RETRY_ATTEMPTS:
        sync_log.status = "DLQ"
        session.add(sync_log)
        session.commit()
        return {"status": "DLQ", "sync_id": sync_log.sync_id}
    
    # Calculate backoff
    backoff = BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** sync_log.attempt_count)
    time.sleep(min(backoff, 30.0))  # Cap at 30s
    
    # Re-attempt
    erp_payload = json.loads(sync_log.erp_response_json) if sync_log.erp_response_json else {}
    result = _attempt_erp_sync(sync_log, erp_payload, dry_run)
    
    sync_log.attempt_count += 1
    sync_log.last_attempt_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    if result["success"]:
        sync_log.status = "SUCCESS"
        sync_log.erp_document_name = result.get("erp_document_name")
        sync_log.erp_response_json = json.dumps(result, ensure_ascii=False)
        sync_log.succeeded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        if sync_log.attempt_count >= MAX_RETRY_ATTEMPTS:
            sync_log.status = "DLQ"
        else:
            sync_log.status = "RETRYING"
        sync_log.last_error = result.get("error")
        sync_log.erp_response_json = json.dumps(result, ensure_ascii=False)
    
    session.add(sync_log)
    session.commit()
    
    return {
        "status": sync_log.status,
        "sync_id": sync_log.sync_id,
        "attempt": sync_log.attempt_count,
    }
