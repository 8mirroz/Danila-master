"""Notifies request owners through outbound channels (honest outbox enqueue)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event
from models import EventType, OutboundMessage, PartRequest

logger = logging.getLogger("automation.jobs.notify_owner")


def _resolve_recipient(payload: dict) -> Optional[str]:
    for key in ("recipient", "owner_email", "owner_contact"):
        value = payload.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _build_body(req: PartRequest) -> str:
    status = getattr(req, "status", None) or "unknown"
    customer = getattr(req, "customer_name", None) or "n/a"
    text = f"PartsOps request {req.request_id}: status={status}, customer={customer}"
    try:
        from delivery import sanitize_for_delivery

        return sanitize_for_delivery(text)
    except Exception:
        return text


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_id = context.request_id or context.payload.get("request_id")
    if not request_id:
        return {"ok": False, "error": "missing_request_id", "notified": False, "queued": False}

    if context.dry_run:
        # Honest: dry_run does not notify and does not enqueue.
        return {"ok": True, "dry_run": True, "notified": False, "queued": False}

    req = session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == context.tenant_id,
        )
    ).first()
    if not req:
        return {"ok": False, "error": "request_not_found", "notified": False, "queued": False}

    recipient = _resolve_recipient(context.payload)
    channel = context.payload.get("channel") or "email"

    if not recipient:
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.STATE_CHANGED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={
                "notification": "skipped",
                "notified": False,
                "queued": False,
                "reason": "missing_recipient",
                "channel": channel,
            },
        )
        return {"ok": False, "error": "missing_recipient", "notified": False, "queued": False}

    idempotency_key = f"notify_owner:{request_id}:{channel}"
    existing = session.exec(
        select(OutboundMessage).where(
            OutboundMessage.tenant_id == context.tenant_id,
            OutboundMessage.idempotency_key == idempotency_key,
        )
    ).first()

    if existing and existing.status in ("pending", "sent", "delivered"):
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.STATE_CHANGED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={
                "notification": "queued",
                "channel": channel,
                "recipient": existing.recipient,
                "outbound_message_id": existing.id,
                "deduped": True,
            },
        )
        return {
            "ok": True,
            "notified": False,
            "queued": True,
            "outbound_message_id": existing.id,
            "deduped": True,
        }

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    subject = f"PartsOps: request {request_id} needs attention"
    body_text = _build_body(req)

    if existing:
        # Re-queue a previously failed/bounced message with same key.
        existing.status = "pending"
        existing.recipient = recipient
        existing.subject = subject
        existing.body_text = body_text
        existing.attempts = 0
        existing.last_error = None
        existing.next_retry_at = None
        existing.updated_at = now
        session.add(existing)
        session.flush()
        msg = existing
    else:
        msg = OutboundMessage(
            tenant_id=context.tenant_id,
            request_id=request_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            idempotency_key=idempotency_key,
            status="pending",
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        session.add(msg)
        session.flush()

    append_request_event(
        session=session,
        request_id=request_id,
        tenant_id=context.tenant_id,
        event_type=EventType.STATE_CHANGED,
        actor_type="automation",
        actor_id=context.actor_id,
        payload={
            "notification": "queued",
            "channel": channel,
            "recipient": recipient,
            "outbound_message_id": msg.id,
        },
    )

    return {
        "ok": True,
        "notified": False,
        "queued": True,
        "outbound_message_id": msg.id,
    }
