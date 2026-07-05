"""
Idempotency helpers.

- stable_request_id(raw) — stable request_id for a given input text.
- idempotency_key_from(request_id, step_name) — per-request step idempotency key.
- is_idempotent(session, model, idempotency_key) — True when an entity exists.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from sqlmodel import Session, select


def _stable_hash(raw: str) -> str:
    if not raw:
        return "none"
    return "REQ-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def stable_request_id(raw: str) -> str:
    return _stable_hash(raw)


def idempotency_key_from(request_id: Optional[str], step_name: str, suffix: str = "") -> str:
    key = f"{request_id or 'unknown'}:{step_name}"
    if suffix:
        key = f"{key}:{suffix}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def is_idempotent(session: Session, model, idempotency_key: str, tenant_id: str) -> bool:
    stmt = (
        select(model)
        .where(model.tenant_id == tenant_id)
        .where(model.idempotency_key == idempotency_key)
        if hasattr(model, "idempotency_key")
        else
        select(model).where(model.tenant_id == tenant_id)  # type: ignore[arg-type]
    )
    return session.exec(stmt).first() is not None


def idempotency_key_for_seed(
    *,
    source: str = "seed",
    channel: str = "batch",
    seed_label: str,
) -> str:
    return f"seed:{source}:{channel}:{hashlib.sha256(seed_label.encode()).hexdigest()[:12]}"
