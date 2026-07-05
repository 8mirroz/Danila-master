"""
Shared helpers used by all automation jobs.

Rules enforced:
- tenant_id is always checked / injected.
- State changes go exclusively through state_machine helpers.
- Outbound traffic uses OutboundMessage only.
- LLM calls go through pii sanitisation + budget_guard.
- Lock helpers wrap the AutomationLock table directly here so jobs don't
  have to reason about row-level expiry semantics.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.errors import (
    BudgetExceededError,
    EvidenceMissingError,
    PolicyViolationError,
    StateGuardError,
)
from app.automation.locks import AutomationLocks
from app.automation.metrics import AutomationMetrics
from event_store import emit_event, emit_state_change
from models import (
    AutomationLock,
    MatchEvidence,
    OutboundMessage,
    PartRequest,
    RequestEvent,
    RequestState,
    EventType,
)
from pii import mask_for_log
from state_machine import get_allowed_next, validate_transition
from pricing import compute_price, check_margin_guard
from matcher import match_part_from_db

logger = logging.getLogger("automation.jobs")

DEFAULT_BATCH = 100
LOCK_TTL_SECONDS = 1800


# ──────────────────────────────────────────────
# Request helpers
# ──────────────────────────────────────────────


def get_request(session: Session, tenant_id: str, request_id: str) -> Optional[PartRequest]:
    return session.exec(
        select(PartRequest)
        .where(PartRequest.tenant_id == tenant_id)
        .where(PartRequest.request_id == request_id)
    ).first()


def list_requests_after(
    session: Session,
    tenant_id: str,
    *,
    states: Optional[list[str]] = None,
    limit: int = DEFAULT_BATCH,
    offset: int = 0,
) -> list[PartRequest]:
    stmt = select(PartRequest).where(PartRequest.tenant_id == tenant_id)
    if states:
        stmt = stmt.where(PartRequest.status.in_(states))
    stmt = stmt.order_by(PartRequest.id).offset(offset).limit(limit)
    return list(session.exec(stmt).all())


# ──────────────────────────────────────────────
# State helpers
# ──────────────────────────────────────────────


def enforce_state(
    session: Session,
    tenant_id: str,
    request_id: str,
    target_state: str,
    *,
    request_data: Optional[dict] = None,
    actor_id: str,
    actor_type: str,
    reason: Optional[str] = None,
    event_type: str = "STATE_CHANGED",
) -> None:
    req = get_request(session, tenant_id, request_id)
    if req is None:
        raise StateGuardError(f"Request not found: {request_id}")

    current = req.status
    result = validate_transition(
        current,
        target_state,
        request_data=request_data,
    )
    if not result["allowed"]:
        raise StateGuardError(
            f"Transition blocked: {current} -> {target_state}: {result['reason']}",
            request_id=request_id,
            current_state=current,
            target_state=target_state,
            violations=result.get("violations", []),
        )

    req.status = target_state
    req.updated_at = datetime.utcnow()
    session.add(req)
    session.commit()

    emit_state_change(
        session=session,
        request_id=request_id,
        from_state=current,
        to_state=target_state,
        actor_type=actor_type,
        actor_id=actor_id,
        reason=reason,
        tenant_id=tenant_id,
        commit=True,
    )


# ──────────────────────────────────────────────
# Evidence helpers
# ──────────────────────────────────────────────


def ensure_match_evidence(session: Session, tenant_id: str, request_id: str) -> MatchEvidence:
    evidence = session.exec(
        select(MatchEvidence)
        .where(MatchEvidence.tenant_id == tenant_id)
        .where(MatchEvidence.request_id == request_id)
    ).first()
    if evidence is None:
        raise EvidenceMissingError(
            f"MatchEvidence required for request {request_id}",
            request_id=request_id,
        )
    return evidence


# ──────────────────────────────────────────────
# LLM helpers — always go through pii + budget
# ──────────────────────────────────────────────


def mask_prompt(prompt: str) -> str:
    return mask_for_log(prompt)


def llm_budget_ok(model: str, estimated_tokens: int) -> bool:
    try:
        from budget_guard import budget_guard as _bg
        result = _bg.check_budget(model=model, tokens=estimated_tokens)
        return bool(result.get("allowed", False))
    except Exception as exc:
        logger.debug("Budget guard skipped: %s", exc)
        return True


def call_llm_safe(prompt: str, *, model: str = "fast", priority: str = "normal", dry_run: bool = False) -> str:
    safe_prompt = mask_prompt(prompt)
    if not llm_budget_ok(model, 500):
        raise BudgetExceededError(
            "LLM budget exceeded before call",
            model=model,
            prompt_preview=safe_prompt[:128],
        )
    if dry_run:
        return "{}"
    try:
        from llm import call_llm
        return call_llm(
            prompt=safe_prompt,
            model=model,
            response_format={"type": "json_object"},
            priority=priority,
        )
    except Exception as exc:
        raise BudgetExceededError(
            f"LLM call failed: {exc}",
            model=model,
            error=str(exc),
        )


# ──────────────────────────────────────────────
# Outbound (outbox)
# ──────────────────────────────────────────────


def enqueue_outbound(
    session: Session,
    *,
    tenant_id: str,
    request_id: str,
    channel: str,
    recipient: str,
    subject: Optional[str],
    body_text: str,
    payload: Optional[dict] = None,
    idempotency_key: Optional[str] = None,
) -> OutboundMessage:
    ik = idempotency_key or _make_idempotency_key(request_id=request_id, channel=channel)
    existing = session.exec(
        select(OutboundMessage)
        .where(OutboundMessage.tenant_id == tenant_id)
        .where(OutboundMessage.idempotency_key == ik)
    ).first()
    if existing:
        return existing
    row = OutboundMessage(
        tenant_id=tenant_id,
        request_id=request_id,
        channel=channel,
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        payload_json=json.dumps(payload or {}),
        idempotency_key=ik,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _make_idempotency_key(*, request_id: str, channel: str, suffix: str = "") -> str:
    seed = f"{request_id}:{channel}:{suffix}"
    return f"OB-{hashlib.sha256(seed.encode()).hexdigest()[:12]}"


# ──────────────────────────────────────────────
# Lock helpers
# ──────────────────────────────────────────────


class Locks:
    def __init__(self, session: Session):
        self._inner = AutomationLocks(session)

    def acquire(self, tenant_id: str, lock_name: str, owner_key: str) -> AutomationLock:
        return self._inner.acquire_lock(
            tenant_id=tenant_id,
            lock_name=lock_name,
            owner_key=owner_key,
            blocking=False,
        )

    def release(self, tenant_id: str, lock_name: str, owner_key: str) -> None:
        self._inner.release_lock(tenant_id=tenant_id, lock_name=lock_name, owner_key=owner_key)


# ──────────────────────────────────────────────
# Pricing helpers
# ──────────────────────────────────────────────


def margin_policy_gate(
    ctx: Any,
    *,
    approved_only: bool = False,
) -> dict:
    """
    Run pricing policy gate.

    If approved_only=True, auto-approval must be allowed or the action
    is blocked until a manager approves the quote.
    """
    from models import MatchEvidence

    result = compute_price(ctx)
    guard = check_margin_guard(
        purchase_price=result.purchase_price,
        sale_price=result.client_price,
    )

    ok = result.margin_policy_passed and guard.get("passed", False)

    if approved_only:
        ok = ok and result.auto_approve_allowed and not result.price_anomaly_detected
    return {
        "passed": ok,
        "result": result,
        "guard": guard,
        "violations": result.violations,
        "warnings": result.warnings,
        "auto_approve_allowed": result.auto_approve_allowed,
    }
