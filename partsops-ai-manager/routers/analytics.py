from fastapi import APIRouter, Depends
from sqlmodel import Session

from database import get_session
from rbac import get_privileged_tenant
from services.quoteops_analytics import quoteops_metrics

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/quoteops")
def get_quoteops_metrics(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    return quoteops_metrics(session, organization_id)
