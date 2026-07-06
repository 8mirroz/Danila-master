from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, Body
from sqlmodel import Session

from database import get_session
from rbac import get_privileged_tenant
from services.request_service import RequestService

router = APIRouter(prefix="/api/erp", tags=["ERP"])


@router.post("/invoice/{request_id}")
def generate_invoice(
    request_id: str,
    body: Optional[dict[str, Any]] = Body(default=None),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return RequestService.generate_invoice(session, request_id, tenant_id, body)
