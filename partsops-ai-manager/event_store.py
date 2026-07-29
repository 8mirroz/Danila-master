"""
PartsOps AI Manager v3 — Event Store.
Append-only request events with tenant-scoped SHA-256 hash chaining.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select, col

from models import EventType, RequestEvent


def _compute_hash(event_data: dict) -> str:
    """SHA-256 hash of canonical event JSON for integrity checks."""
    canonical = json.dumps(event_data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_json_load(raw_value: Optional[str], default):
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return default


def _canonical_hash_input(event: RequestEvent, payload: dict, evidence_refs: list) -> dict:
    return {
        "event_id": event.event_id,
        "tenant_id": event.tenant_id,
        "request_id": event.request_id,
        "event_type": event.event_type,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "occurred_at": event.occurred_at.isoformat(),
        "previous_event_hash": event.previous_event_hash,
        "payload": payload,
        "evidence_refs": evidence_refs,
    }


def _get_last_event_hash(request_id: str, session: Session, tenant_id: Optional[str] = None) -> Optional[str]:
    """Get the most recent event hash for this request and tenant."""
    query = select(RequestEvent).where(RequestEvent.request_id == request_id)
    if tenant_id is not None:
        query = query.where(RequestEvent.tenant_id == tenant_id)
    events = session.exec(query.order_by(col(RequestEvent.id).desc())).all()
    return events[0].event_hash if events else None


def emit_event(
    session: Session,
    request_id: str,
    event_type: str,
    actor_type: str = "system",
    actor_id: str = "system",
    payload: Optional[dict] = None,
    evidence_refs: Optional[list] = None,
    tenant_id: str = "default",
    commit: bool = True,
) -> RequestEvent:
    """Emit an event and link it to the previous tenant-scoped request event."""
    event = RequestEvent(
        event_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        request_id=request_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
        evidence_refs_json=json.dumps(evidence_refs or [], ensure_ascii=False, default=str),
        previous_event_hash=_get_last_event_hash(request_id, session, tenant_id),
    )
    event.event_hash = _compute_hash(_canonical_hash_input(event, payload or {}, evidence_refs or []))

    session.add(event)
    if commit:
        session.commit()
        session.refresh(event)
    return event


def get_events(request_id: str, session: Session, tenant_id: Optional[str] = None) -> list[RequestEvent]:
    """Return all events for a request in chronological order."""
    query = select(RequestEvent).where(RequestEvent.request_id == request_id)
    if tenant_id is not None:
        query = query.where(RequestEvent.tenant_id == tenant_id)
    return list(session.exec(query.order_by(col(RequestEvent.id).asc())).all())


def verify_event_chain(request_id: str, session: Session, tenant_id: Optional[str] = None) -> dict:
    """
    Verify link integrity and persisted content integrity.

    This detects both chain breaks and tampering of payload, actor, timestamp,
    tenant, event type, or evidence refs.
    """
    events = get_events(request_id, session, tenant_id=tenant_id)
    if not events:
        return {"valid": True, "broken_at_event_id": None, "total_events": 0}

    previous_hash = None
    for event in events:
        if event.previous_event_hash != previous_hash:
            return {
                "valid": False,
                "broken_at_event_id": event.event_id,
                "total_events": len(events),
                "reason": f"Цепочка нарушена: ожидался previous_hash={previous_hash}, получен {event.previous_event_hash}",
            }

        payload = _safe_json_load(event.payload_json, {})
        evidence_refs = _safe_json_load(event.evidence_refs_json, [])
        expected_hash = _compute_hash(_canonical_hash_input(event, payload, evidence_refs))
        if event.event_hash != expected_hash:
            return {
                "valid": False,
                "broken_at_event_id": event.event_id,
                "total_events": len(events),
                "reason": "Хеш события не совпадает с persisted content",
                "expected_event_hash": expected_hash,
                "actual_event_hash": event.event_hash,
                "evidence_refs_count": len(evidence_refs),
            }

        previous_hash = event.event_hash

    return {"valid": True, "broken_at_event_id": None, "total_events": len(events)}


def emit_state_change(
    session: Session,
    request_id: str,
    from_state: str,
    to_state: str,
    actor_id: str = "system",
    actor_type: str = "system",
    reason: Optional[str] = None,
    tenant_id: str = "default",
    commit: bool = True,
) -> RequestEvent:
    """Convenience wrapper for STATE_CHANGED events."""
    return emit_event(
        session=session,
        request_id=request_id,
        event_type=EventType.STATE_CHANGED,
        actor_type=actor_type,
        actor_id=actor_id,
        payload={"from": from_state, "to": to_state, "reason": reason},
        tenant_id=tenant_id,
        commit=commit,
    )

def append_request_event(
    session: Session,
    request_id: str,
    tenant_id: str,
    event_type: str,
    actor_type: str = "system",
    actor_id: str = "system",
    payload: Optional[dict] = None,
) -> RequestEvent:
    """Alias for emit_event with tenant_id required."""
    return emit_event(
        session=session,
        request_id=request_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        payload=payload,
        tenant_id=tenant_id,
        commit=False,
    )

