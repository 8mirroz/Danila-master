"""Validates VIN presence and format; enriches with offline WMI decode when possible."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event
from app.automation.engines.vin_query_engine import decode_vin

from models import PartRequest, EventType

logger = logging.getLogger("automation.jobs.intake_validate_vin")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$", re.I)


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_ids = context.payload.get("request_ids") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "validated": 0, "skipped": len(request_ids)}

    validated = 0
    skipped = 0
    for req_id in request_ids:
        row = session.exec(
            select(PartRequest)
            .where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == req_id)
        ).first()
        if not row:
            skipped += 1
            continue

        meta = (context.payload.get("request_metadata") or {}).get(req_id, {}) or {}
        vin = str(meta.get("vin") or getattr(row, "vehicle_vin", None) or "").strip().upper()
        format_ok = bool(VIN_RE.match(vin)) if vin else False

        decode_payload: Dict[str, Any] = {}
        if vin:
            decode_payload = decode_vin(vin)
        else:
            decode_payload = {
                "decoded": False,
                "reason": "empty_vin",
                "partial": True,
                "vin_validity": "invalid",
            }

        append_request_event(
            session=session,
            request_id=req_id,
            tenant_id=context.tenant_id,
            event_type=EventType.VIN_VALIDATED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={
                "valid": format_ok and decode_payload.get("vin_validity") == "valid",
                "format_ok": format_ok,
                "vin": vin or None,
                "decode": {
                    "make": decode_payload.get("make"),
                    "model": decode_payload.get("model"),
                    "year": decode_payload.get("year"),
                    "vin_validity": decode_payload.get("vin_validity"),
                    "partial": decode_payload.get("partial"),
                    "source": decode_payload.get("source"),
                    "reason": decode_payload.get("reason"),
                    "implemented": decode_payload.get("implemented"),
                },
            },
        )
        validated += 1
    return {"ok": True, "validated": validated, "skipped": skipped}
