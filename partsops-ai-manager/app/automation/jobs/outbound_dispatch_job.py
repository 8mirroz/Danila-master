"""
Dispatches pending outbound messages with retry/backoff logic.
Handles email, telegram, webhook channels via existing adapters.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_system_event
from models import OutboundMessage, PartRequest
from delivery import EmailAdapter, TelegramAdapter
from event_store import EventType

logger = logging.getLogger("automation.jobs.outbound_dispatcher")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    """
    Process pending outbound messages that are due for retry.
    
    Expected payload:
    {
        "channel": "email|telegram|webhook|all",  # optional, filter by channel
        "batch_size": 50,  # optional
        "max_attempts": 3,  # optional, override default
    }
    """
    channel_filter = context.payload.get("channel", "all")
    batch_size = context.payload.get("batch_size", 50)
    max_attempts = context.payload.get("max_attempts", 3)
    
    if context.dry_run:
        return {"ok": True, "dry_run": True, "dispatched": 0}

    # Build query for pending messages ready for retry
    now = datetime.utcnow()
    query = select(OutboundMessage).where(
        OutboundMessage.tenant_id == context.tenant_id,
        OutboundMessage.status.in_(["pending", "failed"]),
        OutboundMessage.attempts < OutboundMessage.max_attempts,
    )
    
    # Filter by next_retry_at if set
    query = query.where(
        (OutboundMessage.next_retry_at == None) | (OutboundMessage.next_retry_at <= now)
    )
    
    # Filter by channel if specified
    if channel_filter != "all":
        query = query.where(OutboundMessage.channel == channel_filter)
    
    query = query.order_by(OutboundMessage.created_at).limit(batch_size)
    
    messages = session.exec(query).all()
    
    dispatched = 0
    failed = 0
    skipped = 0
    
    for msg in messages:
        try:
            # Get request for context (invoice reference, etc.)
            request = None
            if msg.request_id:
                request = session.exec(
                    select(PartRequest).where(PartRequest.request_id == msg.request_id)
                ).first()
            
            success = False
            error_msg = None
            
            if msg.channel == "email":
                if request and request.customer_email_masked:
                    # Send via EmailAdapter
                    from suppliers import Invoice
                    invoice = session.exec(
                        select(Invoice).where(Invoice.request_id == msg.request_id)
                    ).first()
                    if invoice:
                        result = EmailAdapter.send_invoice(
                            invoice=invoice,
                            recipient_email=msg.recipient,
                            session=session,
                            tenant_id=context.tenant_id,
                            dry_run=context.dry_run,
                        )
                        success = result.status == "sent"
                        if not success:
                            error_msg = result.last_error
                    else:
                        error_msg = "No invoice found for request"
                else:
                    error_msg = "No email recipient or request"
                    
            elif msg.channel == "telegram":
                if msg.recipient and msg.recipient != "unknown":
                    from suppliers import Invoice
                    invoice = session.exec(
                        select(Invoice).where(Invoice.request_id == msg.request_id)
                    ).first()
                    if invoice:
                        result = TelegramAdapter.send_invoice_preview(
                            invoice=invoice,
                            chat_id=msg.recipient,
                            session=session,
                            tenant_id=context.tenant_id,
                            dry_run=context.dry_run,
                        )
                        success = result.status == "sent"
                        if not success:
                            error_msg = result.last_error
                    else:
                        error_msg = "No invoice found for request"
                else:
                    error_msg = "No valid telegram chat_id"
                    
            elif msg.channel == "webhook":
                # Webhook delivery - would need httpx call
                logger.warning(f"Webhook delivery not fully implemented for {msg.id}")
                error_msg = "Webhook delivery not implemented"
                
            else:
                error_msg = f"Unknown channel: {msg.channel}"
            
            # Update message status
            msg.attempts += 1
            msg.updated_at = now
            
            if success:
                msg.status = "sent"
                msg.sent_at = now
                dispatched += 1
            elif msg.attempts >= msg.max_attempts:
                msg.status = "failed"
                msg.last_error = error_msg or "Max attempts reached"
                failed += 1
                
                # Emit dead letter event
                append_system_event(
                    session=session,
                    tenant_id=context.tenant_id,
                    event_type="outbound.dead_letter",
                    actor_type="automation",
                    actor_id=context.actor_id,
                    payload={
                        "message_id": msg.id,
                        "channel": msg.channel,
                        "recipient": msg.recipient,
                        "attempts": msg.attempts,
                        "error": msg.last_error,
                        "request_id": msg.request_id,
                    },
                )
            else:
                msg.status = "pending"
                # Exponential backoff: 1min, 5min, 15min, 30min, 1hr...
                backoff_minutes = min(5 ** msg.attempts, 60)
                msg.next_retry_at = now + timedelta(minutes=backoff_minutes)
                failed += 1
            
            session.add(msg)
            
        except Exception as e:
            logger.exception(f"Error dispatching message {msg.id}")
            msg.attempts += 1
            msg.last_error = str(e)
            msg.status = "failed" if msg.attempts >= msg.max_attempts else "pending"
            session.add(msg)
            skipped += 1
    
    session.commit()
    
    return {"ok": True, "dispatched": dispatched, "failed": failed, "skipped": skipped, "total": len(messages)}