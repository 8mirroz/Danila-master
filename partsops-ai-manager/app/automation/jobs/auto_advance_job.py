"""Auto advances requests to READY_FOR_APPROVAL if they pass all gates automatically."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict
from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event
from policy_engine import policy_engine
from models import PartRequest, RequestState, EventType
from state_machine import transition as sm_transition

logger = logging.getLogger("automation.jobs.auto_advance")

def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True}

    requests = session.exec(
        select(PartRequest).where(PartRequest.tenant_id == context.tenant_id)
        .where(PartRequest.status == RequestState.PART_EXTRACTION)
    ).all()

    advanced = 0
    for req in requests:
        if policy_engine.auto_advance_policy(req, session):
            old_state = req.status
            try:
                # Advance step-by-step through permitted transitions
                state = old_state
                for target_state in [
                    RequestState.MATCHING, 
                    RequestState.SUPPLIER_SEARCH, 
                    RequestState.OFFER_RANKING, 
                    RequestState.PRICING_REVIEW, 
                    RequestState.READY_FOR_APPROVAL
                ]:
                    state = sm_transition(state, target_state, req.model_dump())
                
                req.status = state
                req.updated_at = datetime.utcnow()
                session.add(req)
                
                append_request_event(
                    session=session,
                    request_id=req.request_id,
                    tenant_id=context.tenant_id,
                    event_type=EventType.STATE_CHANGED,
                    actor_type="automation",
                    actor_id=context.actor_id,
                    payload={"from": old_state, "to": state, "reason": "Auto-advanced step-by-step by policy engine"},
                )
                advanced += 1
            except Exception as e:
                logger.error("Failed to auto-advance request %s: %s", req.request_id, e)
            
    if advanced > 0:
        session.commit()

    return {"ok": True, "advanced_count": advanced}
