"""
Tracing + transport helper for the automation layer.

Forwards everything to `emit_event`, with stable tie-out:
- every request event gets `request_id` and `tenant_id` in payload;
- every system event gets `request_id`, `correlation_id`, `tenant_id`;
- runner emits `job.started`/`job.finished` with `correlation_id`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlmodel import Session

from event_store import emit_event

logger = logging.getLogger("automation.events")


def append_request_event(
    session: Session,
    *,
    request_id: str,
    tenant_id: str,
    event_type: str,
    actor_type: str,
    actor_id: str,
    payload: Optional[Dict[str, Any]] = None,
    evidence_refs: Optional[List[str]] = None,
    commit: bool = True,
) -> Any:
    """Emit a request event with request_id + tenant_id mirrored in payload."""
    payload = {
        "request_id": request_id,
        "tenant_id": tenant_id,
        **(payload or {}),
    }
    return emit_event(
        session=session,
        request_id=request_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        payload=payload,
        evidence_refs=evidence_refs,
        tenant_id=tenant_id,
        commit=commit,
    )


def append_system_event(
    session: Session,
    *,
    tenant_id: str,
    event_type: str,
    actor_type: str = "automation",
    actor_id: str = "system",
    payload: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    evidence_refs: Optional[List[str]] = None,
    commit: bool = True,
) -> Any:
    """Emit an automation-level system event tied to a request when known."""
    payload = {
        "request_id": request_id,
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        **(payload or {}),
    }
    return emit_event(
        session=session,
        request_id=request_id or "__system__",
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        payload=payload,
        evidence_refs=evidence_refs,
        tenant_id=tenant_id,
        commit=commit,
    )
