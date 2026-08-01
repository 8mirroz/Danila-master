"""Multi-channel notification engine — honest outbox enqueue, never silent success."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def notify(
    recipient: Any,
    message: Any,
    *,
    channel: str = "email",
    session=None,
    tenant_id: str = "default",
    request_id: Optional[str] = None,
) -> dict:
    """
    Enqueue a notification or report partial/error honestly.

    - No recipient → error, sent=False
    - session + recipient → OutboundMessage pending (queued, not sent)
    - no session → partial, log only
    """
    recipient_str = str(recipient).strip() if recipient is not None else ""
    body = str(message) if message is not None else ""
    channel = channel or "email"

    if not recipient_str:
        return {
            "implemented": True,
            "status": "error",
            "reason": "missing_recipient",
            "sent": False,
            "queued": False,
            "ok": False,
        }

    if session is not None:
        try:
            from models import OutboundMessage
        except Exception as exc:  # pragma: no cover
            return {
                "implemented": True,
                "status": "error",
                "reason": f"outbound_model_unavailable:{exc}",
                "sent": False,
                "queued": False,
                "ok": False,
            }

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rid = request_id or "none"
        idempotency_key = f"notify:{tenant_id}:{rid}:{channel}:{uuid.uuid4().hex[:12]}"
        subject = f"PartsOps notification ({channel})"
        if request_id:
            subject = f"PartsOps: request {request_id}"

        msg = OutboundMessage(
            tenant_id=tenant_id or "default",
            request_id=request_id,
            channel=channel,
            recipient=recipient_str,
            subject=subject,
            body_text=body,
            idempotency_key=idempotency_key,
            status="pending",
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        session.add(msg)
        session.flush()

        return {
            "implemented": True,
            "status": "ok",
            "reason": None,
            "sent": False,
            "queued": True,
            "ok": True,
            "outbound_message_id": msg.id,
            "channel": channel,
            "recipient": recipient_str,
        }

    try:
        from pii import mask_email, mask_for_log

        safe_recipient = (
            mask_email(recipient_str) if "@" in recipient_str else f"{recipient_str[:3]}***"
        )
        safe_body = mask_for_log(body[:200])
    except Exception:  # pragma: no cover
        safe_recipient = f"{recipient_str[:3]}***" if recipient_str else ""
        safe_body = "[redacted]"

    logger.info(
        "notify log-only (no session): channel=%s recipient=%s message=%s",
        channel,
        safe_recipient,
        safe_body,
    )
    return {
        "implemented": True,
        "status": "partial",
        "reason": "no_session_queued_log_only",
        "sent": False,
        "queued": False,
        "ok": True,
        "channel": channel,
        "recipient": recipient_str,
    }
