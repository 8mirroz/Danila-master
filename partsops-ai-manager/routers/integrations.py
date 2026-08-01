from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_session
from rbac import CurrentPrincipal, get_current_principal, get_privileged_tenant
from services.service_api_keys import create_key, list_keys, revoke_key, verify_key

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


class ServiceKeyPayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] = Field(min_length=1)


def _key_view(key):
    return {
        "key_id": key.key_id,
        "name": key.name,
        "scopes": json.loads(key.scopes_json),
        "status": key.status,
        "created_at": key.created_at.isoformat(),
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
    }


@router.get("/service-keys")
def get_service_keys(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    if principal.role not in {"admin", "platform_admin"}:
        raise HTTPException(403, "Only administrators can manage service keys")
    return [_key_view(key) for key in list_keys(session, organization_id)]


@router.post("/service-keys", status_code=201)
def issue_service_key(
    payload: ServiceKeyPayload,
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    if principal.role not in {"admin", "platform_admin"}:
        raise HTTPException(403, "Only administrators can manage service keys")
    key, raw_key = create_key(session, organization_id, payload.name, payload.scopes)
    return {**_key_view(key), "secret": raw_key}


@router.post("/service-keys/{key_id}/revoke")
def revoke_service_key(
    key_id: str,
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    if principal.role not in {"admin", "platform_admin"}:
        raise HTTPException(403, "Only administrators can manage service keys")
    return _key_view(revoke_key(session, organization_id, key_id))


@router.get("/service-session")
def service_session(
    x_partsops_service_key: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_session),
):
    if not x_partsops_service_key:
        raise HTTPException(401, "X-PartsOps-Service-Key is required")
    key = verify_key(session, x_partsops_service_key, "erp:read")
    return {
        "organization_id": key.organization_id,
        "scopes": json.loads(key.scopes_json),
        "key_id": key.key_id,
    }
