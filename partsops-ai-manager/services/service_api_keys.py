from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from models import ServiceApiKey

ALLOWED_SCOPES = {"erp:read", "erp:write", "webhooks:write"}


def create_key(
    session: Session, organization_id: str, name: str, scopes: list[str]
) -> tuple[ServiceApiKey, str]:
    normalized = sorted(set(scopes))
    if not normalized or not set(normalized).issubset(ALLOWED_SCOPES):
        raise HTTPException(422, "Unsupported service key scope")
    key_id = f"sk_{uuid.uuid4().hex[:12]}"
    secret = secrets.token_urlsafe(32)
    raw = f"partsops_{key_id}_{secret}"
    key = ServiceApiKey(
        key_id=key_id,
        organization_id=organization_id,
        name=name.strip(),
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        scopes_json=json.dumps(normalized),
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return key, raw


def list_keys(session: Session, organization_id: str) -> list[ServiceApiKey]:
    return session.exec(
        select(ServiceApiKey).where(ServiceApiKey.organization_id == organization_id)
    ).all()


def revoke_key(session: Session, organization_id: str, key_id: str) -> ServiceApiKey:
    key = session.exec(
        select(ServiceApiKey).where(
            ServiceApiKey.organization_id == organization_id,
            ServiceApiKey.key_id == key_id,
        )
    ).first()
    if not key:
        raise HTTPException(404, "Service key not found")
    key.status = "revoked"
    key.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(key)
    session.commit()
    session.refresh(key)
    return key


def verify_key(session: Session, raw_key: str, scope: str) -> ServiceApiKey:
    digest = hashlib.sha256(raw_key.encode()).hexdigest()
    key = session.exec(
        select(ServiceApiKey).where(
            ServiceApiKey.key_hash == digest, ServiceApiKey.status == "active"
        )
    ).first()
    if not key or scope not in json.loads(key.scopes_json):
        raise HTTPException(403, "Service key is invalid or lacks required scope")
    key.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(key)
    session.commit()
    session.refresh(key)
    return key
