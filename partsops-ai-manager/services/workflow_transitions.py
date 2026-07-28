"""State-machine-only request transitions shared by pipeline agents."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Iterable

from sqlmodel import Session

from event_store import emit_state_change
from models import ALLOWED_TRANSITIONS, PartRequest
from state_machine import StateMachineError, validate_transition


def _value(state: object) -> str:
    return str(getattr(state, "value", state))


def _path(current: str, target: str) -> list[str]:
    if current == target:
        return []
    queue: deque[tuple[str, list[str]]] = deque([(current, [])])
    visited = {current}
    while queue:
        state, steps = queue.popleft()
        for candidate in ALLOWED_TRANSITIONS.get(state, []):
            candidate_value = _value(candidate)
            if candidate_value in visited:
                continue
            next_steps = [*steps, candidate_value]
            if candidate_value == target:
                return next_steps
            visited.add(candidate_value)
            queue.append((candidate_value, next_steps))
    raise StateMachineError(f"No legal transition path: {current} -> {target}")


def advance_request_state(
    session: Session,
    request: PartRequest,
    target_state: object,
    *,
    actor_id: str,
    reason: str,
) -> PartRequest:
    """Advance through every legal state, emitting an audit event per step."""
    current = _value(request.status)
    target = _value(target_state)
    for next_state in _path(current, target):
        result = validate_transition(current, next_state, request.model_dump(), strict_invariants=True)
        if not result["allowed"]:
            raise StateMachineError(f"{result['reason']}. Нарушения: {result['violations']}")
        request.status = next_state
        request.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(request)
        emit_state_change(
            session=session,
            request_id=request.request_id,
            from_state=current,
            to_state=next_state,
            actor_type="agent",
            actor_id=actor_id,
            reason=reason,
            tenant_id=request.tenant_id,
            commit=False,
        )
        current = next_state
    session.commit()
    session.refresh(request)
    return request
