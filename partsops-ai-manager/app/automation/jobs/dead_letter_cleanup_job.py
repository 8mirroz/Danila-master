"""Retention cleanup of dead-letter OutboundMessages (failed + exhausted only)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_system_event
from models import OutboundMessage

logger = logging.getLogger("automation.jobs.dead_letter_cleanup")


def _dead_letter_rows(session: Session, tenant_id: str, cutoff: datetime) -> List[OutboundMessage]:
    """Select exhausted failed messages older than cutoff. Never touches pending/sent."""
    rows = session.exec(
        select(OutboundMessage).where(
            OutboundMessage.tenant_id == tenant_id,
            OutboundMessage.status == "failed",
            OutboundMessage.attempts >= OutboundMessage.max_attempts,
        )
    ).all()
    selected: List[OutboundMessage] = []
    for row in rows:
        ts = row.updated_at or row.created_at
        if ts is not None and ts < cutoff:
            selected.append(row)
    return selected


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    retention_hours = int(context.payload.get("retention_hours", 72))
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=retention_hours)
    candidates = _dead_letter_rows(session, context.tenant_id, cutoff)
    count = len(candidates)

    if context.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would_remove": count,
            "removed": 0,
            "retention_hours": retention_hours,
            "cutoff": cutoff.isoformat(),
        }

    removed = 0
    for row in candidates:
        session.delete(row)
        removed += 1
    if removed:
        session.flush()

    append_system_event(
        session=session,
        tenant_id=context.tenant_id,
        event_type="dead_letter.cleanup.finished",
        actor_type="automation",
        actor_id=context.actor_id,
        payload={
            "retention_hours": retention_hours,
            "removed": removed,
            "cutoff": cutoff.isoformat(),
        },
    )
    return {
        "ok": True,
        "removed": removed,
        "retention_hours": retention_hours,
        "cutoff": cutoff.isoformat(),
    }
