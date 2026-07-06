from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from database import get_session
from rbac import get_privileged_tenant
from models import LLMUsageLog
from state_machine import get_allowed_next, is_terminal
from learning import calculate_system_accuracy

router = APIRouter(prefix="/api", tags=["Observability & System"])


@router.get("/state-machine/{state}")
def get_state_machine_state(state: str):
    return {
        "state": state,
        "allowed_next": get_allowed_next(state),
        "is_terminal": is_terminal(state),
    }


@router.get("/admin/observability/traces")
def get_observability_traces(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    logs = session.exec(
        select(LLMUsageLog).where(LLMUsageLog.tenant_id == tenant_id).order_by(LLMUsageLog.id.desc())
    ).all()
    return [
        {
            "correlation_id": log.correlation_id,
            "provider": log.provider,
            "model": log.model,
            "status": log.status,
            "latency_ms": log.latency_ms,
            "total_tokens": log.total_tokens,
            "cost_usd": log.cost_usd,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/admin/observability/llm-costs")
def get_observability_llm_costs(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    logs = session.exec(select(LLMUsageLog).where(LLMUsageLog.tenant_id == tenant_id)).all()
    total_cost = round(sum(log.cost_usd for log in logs), 10)
    by_provider: dict[str, float] = {}
    by_model: dict[str, float] = {}
    for log in logs:
        by_provider[log.provider] = by_provider.get(log.provider, 0.0) + log.cost_usd
        by_model[log.model] = by_model.get(log.model, 0.0) + log.cost_usd
    return {
        "count": len(logs),
        "total_cost_usd": total_cost,
        "by_provider": {key: round(value, 10) for key, value in by_provider.items()},
        "by_model": {key: round(value, 10) for key, value in by_model.items()},
    }


@router.get("/system/accuracy")
def get_system_accuracy(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return calculate_system_accuracy(session, tenant_id)
