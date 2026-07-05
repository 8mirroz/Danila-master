"""Notifies request owners through outbound channels."""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlmodel import Session

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.notify_owner")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_id = context.request_id or context.payload.get("request_id")
    if not request_id:
        return {"ok": False, "error": "missing_request_id"}
    if context.dry_run:
        return {"ok": True, "dry_run": True, "notified": True}

    append_request_event(
        session=session,
        request_id=request_id,
        tenant_id=context.tenant_id,
        event_type=EventType.STATE_CHANGED,
        actor_type="automation",
        actor_id=context.actor_id,
        payload={"notification": True, "channel": context.payload.get("channel", "email")},
    )
    return {"ok": True, "notified": True}
