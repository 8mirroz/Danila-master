"""Escalation routing engine — records STATE_CHANGED when session is available."""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def escalate(issue: Any) -> dict:
    """
    Escalate an issue by writing a request event when session + request_id exist.

    Does not claim external paging/alerts completed.
    """
    data: Dict[str, Any] = issue if isinstance(issue, dict) else {}
    request_id = data.get("request_id")
    tenant_id = data.get("tenant_id") or "default"
    reason = data.get("reason") or "escalation"
    session = data.get("session")
    actor_id = data.get("actor_id") or "escalation_engine"

    if session is None or not request_id:
        return {
            "implemented": True,
            "status": "partial",
            "reason": "missing_session_or_request_id",
            "escalated": False,
            "ok": True,
        }

    try:
        from models import EventType
        from app.automation.events import append_request_event

        append_request_event(
            session=session,
            request_id=str(request_id),
            tenant_id=str(tenant_id),
            event_type=EventType.STATE_CHANGED,
            actor_type="automation",
            actor_id=str(actor_id),
            payload={
                "escalated": True,
                "reason": reason,
            },
        )
    except Exception as exc:
        logger.exception("escalate failed for %s", request_id)
        return {
            "implemented": True,
            "status": "error",
            "reason": str(exc),
            "escalated": False,
            "ok": False,
            "request_id": request_id,
        }

    return {
        "implemented": True,
        "status": "ok",
        "reason": None,
        "escalated": True,
        "ok": True,
        "request_id": request_id,
        "tenant_id": tenant_id,
    }
