from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from database import get_session
from rbac import get_privileged_tenant
from matcher import match_part_from_db

router = APIRouter(prefix="/api/catalog", tags=["Catalog"])


@router.get("/search")
def catalog_search(
    q: str = Query(..., min_length=2),
    threshold: float = Query(default=50.0),
    limit: int = Query(default=5, ge=1, le=25),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    matches = match_part_from_db(q, session, threshold=threshold, limit=limit, tenant_id=tenant_id)
    return {"query": q, "total": len(matches), "matches": matches}
