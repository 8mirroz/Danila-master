"""SLA Watchdog Job — monitors stalled requests and triggers alerts/escalations."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event
from models import PartRequest, RequestState, EventType

logger = logging.getLogger("automation.jobs.sla_watchdog")

def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    five_min_ago = (now - timedelta(minutes=5)).isoformat()
    two_hours_ago = (now - timedelta(hours=2)).isoformat()

    stalled_matching = session.exec(
        select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
        .where(PartRequest.status == RequestState.MATCHING)
        .where(PartRequest.updated_at < five_min_ago)
    ).all()

    stalled_approval = session.exec(
        select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
        .where(PartRequest.status == RequestState.READY_FOR_APPROVAL)
        .where(PartRequest.updated_at < two_hours_ago)
    ).all()

    alerts_triggered = 0

    for req in stalled_matching:
        append_request_event(
            session=session,
            request_id=req.request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.SLA_BREACHED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"status": req.status, "reason": "Matching phase took longer than 5 minutes. High latency alert."},
        )
        alerts_triggered += 1

    for req in stalled_approval:
        append_request_event(
            session=session,
            request_id=req.request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.SLA_BREACHED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"status": req.status, "reason": "Stalled in READY_FOR_APPROVAL for more than 2 hours. Escalated to manager."},
        )
        alerts_triggered += 1

    if alerts_triggered > 0:
        session.commit()

    return {"ok": True, "alerts_triggered": alerts_triggered}
