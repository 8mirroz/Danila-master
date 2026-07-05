"""Validates VIN presence and format before downstream matching."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.intake_validate_vin")
VIN_RE = re.compile(r"^[A-Z0-9]{17}$")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_ids = context.payload.get("request_ids") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "validated": 0, "skipped": len(request_ids)}

    validated = 0
    skipped = 0
    for req_id in request_ids:
        row = session.exec(
            select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == req_id)
        ).first()
        if not row:
            skipped += 1
            continue
        vin = (context.payload.get("request_metadata") or {}).get(req_id, {}).get("vin", "")
        valid = bool(VIN_RE.match(vin))
        append_request_event(
            session=session,
            request_id=req_id,
            tenant_id=context.tenant_id,
            event_type=EventType.VIN_VALIDATED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"valid": valid, "vin": vin},
        )
        validated += 1
    return {"ok": True, "validated": validated, "skipped": skipped}
