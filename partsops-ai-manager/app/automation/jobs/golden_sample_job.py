"""Creates golden samples from approved manual corrections."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event

from models import PartRequest, EventType, GoldenSample

logger = logging.getLogger("automation.jobs.golden_sample")


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    samples = context.payload.get("samples") or []
    if context.dry_run:
        return {"ok": True, "dry_run": True, "created": 0, "skipped": len(samples)}

    created = 0
    skipped = 0
    for sample in samples:
        request_id = sample.get("request_id")
        if not request_id:
            skipped += 1
            continue
        row = session.exec(
            select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
            .where(PartRequest.request_id == request_id)
        ).first()
        if not row:
            skipped += 1
            continue
        golden = GoldenSample(
            tenant_id=context.tenant_id,
            sample_id=f"GS-{uuid.uuid4().hex[:8].upper()}",
            request_id=request_id,
            source_text=sample.get("source_text", ""),
            corrected_parts_json=sample.get("corrected_parts_json", "[]"),
            corrected_vehicle_json=sample.get("corrected_vehicle_json"),
            correction_reason_tags=sample.get("correction_reason_tags"),
            approved_by=context.actor_id,
        )
        session.add(golden)
        session.commit()
        session.refresh(golden)
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type=EventType.MANUAL_CORRECTION_SAVED,
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"golden_sample_id": golden.sample_id},
        )
        created += 1
    return {"ok": True, "created": created, "skipped": skipped}
