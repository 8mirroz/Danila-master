from __future__ import annotations

import asyncio
import hmac
import json
from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func, desc

from database import get_session, engine
from rbac import get_privileged_tenant, CurrentPrincipal, _get_api_token, _parse_bearer_token, verify_signed_token, _normalize_role, DEFAULT_TENANT
from models import LLMUsageLog, PartRequest
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


@router.get("/admin/observability/metrics")
def get_observability_metrics(
  session: Session = Depends(get_session),
  tenant_id: str = Depends(get_privileged_tenant),
):
  logs = session.exec(select(LLMUsageLog).where(LLMUsageLog.tenant_id == tenant_id)).all()
  total_cost = round(sum(log.cost_usd for log in logs), 10)
  rpm = round(len(logs) / 60.0, 3) if logs else 0.0
  error_logs = [log for log in logs if (log.status or "").lower() != "success"]
  return {
    "rpm_estimate": rpm,
    "error_rate": len(error_logs) / len(logs) if logs else 0.0,
    "llm_cost_usd": total_cost,
    "llm_requests": len(logs),
  }


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


@router.get("/admin/observability/pipeline-runs")
def get_pipeline_runs(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    limit: int = 20,
    correlation_id: str | None = None,
):
    """Get pipeline runs grouped by correlation_id with phase details."""
    from sqlmodel import func, desc
    
    # Subquery: latest LLMUsageLog per correlation_id
    latest_logs = session.exec(
        select(
            LLMUsageLog.correlation_id,
            func.max(LLMUsageLog.id).label("max_id")
        )
        .where(LLMUsageLog.tenant_id == tenant_id)
        .group_by(LLMUsageLog.correlation_id)
        .order_by(desc("max_id"))
        .limit(limit)
    ).all()
    
    runs = []
    for corr_id, _ in latest_logs:
        if not corr_id:
            continue
        phase_logs = session.exec(
            select(LLMUsageLog)
            .where(LLMUsageLog.tenant_id == tenant_id)
            .where(LLMUsageLog.correlation_id == corr_id)
            .order_by(LLMUsageLog.created_at)
        ).all()
        
        if not phase_logs:
            continue
            
        phases = {}
        for log in phase_logs:
            key = log.provider  # or model
            phases[key] = {
                "agent_type": log.provider,
                "success": (log.status or "").lower() == "success",
                "execution_time_ms": log.latency_ms,
                "correlation_id": log.correlation_id,
                "latency_ms": log.latency_ms,
                "total_tokens": log.total_tokens,
                "cost_usd": log.cost_usd,
                "provider": log.provider,
                "model": log.model,
                "errors": [] if (log.status or "").lower() == "success" else [log.status or "unknown error"],
            }
        
        runs.append({
            "request_id": corr_id[:16],
            "correlation_id": corr_id,
            "status": "completed" if all(p["success"] for p in phases.values()) else "in_progress",
            "phases": phases,
        })
    
    return runs


@router.get("/admin/observability/pipeline-runs/{correlation_id}")
def get_pipeline_run_detail(
    correlation_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """Get full trace detail for a single pipeline run."""
    logs = session.exec(
        select(LLMUsageLog)
        .where(LLMUsageLog.tenant_id == tenant_id)
        .where(LLMUsageLog.correlation_id == correlation_id)
        .order_by(LLMUsageLog.created_at)
    ).all()
    
    if not logs:
        return {"detail": "Not found"}
    
    phases = {}
    for log in logs:
        key = log.provider
        phases[key] = {
            "agent_type": log.provider,
            "success": (log.status or "").lower() == "success",
            "execution_time_ms": log.latency_ms,
            "correlation_id": log.correlation_id,
            "latency_ms": log.latency_ms,
            "total_tokens": log.total_tokens,
            "cost_usd": log.cost_usd,
            "provider": log.provider,
            "model": log.model,
            "errors": [] if (log.status or "").lower() == "success" else [log.status or "unknown error"],
            "data": log.raw_prompt if hasattr(log, 'raw_prompt') else None,
        }
    
    return {
        "correlation_id": correlation_id,
        "phases": phases,
    }


@router.get("/system/accuracy")
def get_system_accuracy(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return calculate_system_accuracy(session, tenant_id)


@router.post("/admin/observability/vault-sync/{correlation_id}")
def trigger_vault_sync(
    correlation_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """Trigger vault sync for a specific pipeline run."""
    from vault_sync import sync_pipeline_run
    from sqlmodel import func, desc
    
    # Get all logs for this correlation_id
    phase_logs = session.exec(
        select(LLMUsageLog)
        .where(LLMUsageLog.tenant_id == tenant_id)
        .where(LLMUsageLog.correlation_id == correlation_id)
        .order_by(LLMUsageLog.created_at)
    ).all()
    
    if not phase_logs:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Build phase data
    phases = {}
    for log in phase_logs:
        key = log.provider
        phases[key] = {
            "agent_type": log.provider,
            "provider": log.provider,
            "model": log.model,
            "success": (log.status or "").lower() == "success",
            "latency_ms": log.latency_ms,
            "total_tokens": log.total_tokens,
            "cost_usd": log.cost_usd,
            "errors": [] if (log.status or "").lower() == "success" else [log.status or "unknown error"],
        }
    
    # Determine overall status
    all_success = all(p["success"] for p in phases.values())
    run_status = "completed" if all_success else "in_progress"
    
    run_data = {
        "correlation_id": correlation_id,
        "status": run_status,
        "phases": phases,
        "synced_at": datetime.now().isoformat(),
    }
    
    try:
        result_path = sync_pipeline_run(correlation_id, run_data)
        return {"status": "success", "vault_path": result_path}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Vault sync failed: {e}")


# SSE endpoint for real-time updates
@router.get("/events/stream")
async def sse_stream(request: Request, tenant_id: Optional[str] = None):
    """Server-Sent Events stream for real-time updates: queue changes, LLM costs, system metrics.

    Supports two authentication modes:
    - Bearer token via Authorization header (preferred)
    - Bearer token as `token` query param together with `tenant_id` (for EventSource)
    """

    def _build_principal_from_token(token: Optional[str], secret: str) -> Optional[CurrentPrincipal]:
        if not token:
            return None
        claims = verify_signed_token(token, secret)
        if claims:
            tenant_id_claim, role_claim = claims
            return CurrentPrincipal(
                tenant_id=tenant_id_claim,
                role=_normalize_role(role_claim),
                authenticated=True,
                auth_mode="token",
            )
        if hmac.compare_digest(token, secret):
            return CurrentPrincipal(
                tenant_id=(tenant_id or DEFAULT_TENANT),
                role=_normalize_role(None),
                authenticated=True,
                auth_mode="token",
            )
        return None

    secret = _get_api_token()
    auth_header = request.headers.get("authorization")
    query_token = request.query_params.get("token")
    resolved_tenant = tenant_id or request.query_params.get("tenant_id")

    if secret:
        principal = None
        if auth_header:
            principal = _build_principal_from_token(_parse_bearer_token(auth_header), secret)
        elif query_token:
            principal = _build_principal_from_token(query_token, secret)
        else:
            principal = CurrentPrincipal(
                tenant_id=DEFAULT_TENANT,
                role=_normalize_role(None),
                authenticated=False,
                auth_mode="token",
            )

        if principal.auth_mode == "token" and not principal.authenticated:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer ***")

        if principal.auth_mode != "token" and not principal.authenticated:
          from fastapi import HTTPException
          raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer ***")

          stream_tenant = principal.tenant_id
        else:
          stream_tenant = resolved_tenant or DEFAULT_TENANT

        visited_corr_cache: set[str] = set()

        async def event_generator():
          last_request_count = 0
          last_llm_cost = 0.0
          last_llm_count = 0
          visited_corr_cache.clear()

          while True:
            if await request.is_disconnected():
              break

            with Session(engine) as session:
              # Get current request count
              requests = session.exec(select(PartRequest).where(PartRequest.tenant_id == stream_tenant)).all()
              request_count = len(requests)

              # Get LLM costs
              logs = session.exec(select(LLMUsageLog).where(LLMUsageLog.tenant_id == stream_tenant)).all()
              llm_cost = round(sum(log.cost_usd for log in logs), 10)
              llm_count = len(logs)

              # Send events only when data changes
              events = []

              status_counts = {status: sum(1 for r in requests if r.status == status) for status in ["NEW", "PART_EXTRACTION", "OFFER_MATCHING", "APPROVAL_GATE", "APPROVED", "INVOICE_DRAFTED", "ERP_SYNC", "CLOSED", "CANCELLED"]}
              
              if request_count != last_request_count or status_counts != getattr(event_generator, 'last_status_counts', None):
                events.append({
                  "type": "requests_updated",
                  "data": {
                    "total": request_count,
                    "by_status": status_counts,
                    "timestamp": datetime.now().isoformat()
                  }
                })
                last_request_count = request_count
                event_generator.last_status_counts = status_counts

              if llm_cost != last_llm_cost or llm_count != last_llm_count:
                events.append({
                  "type": "llm_cost_updated",
                  "data": {
                    "total_cost_usd": llm_cost,
                    "total_requests": llm_count
                  }
                })
                last_llm_cost = llm_cost
                last_llm_count = llm_count

              # Pipeline runs: new correlation_id or status change
              recent_corrs: dict[str, dict] = {}
              for log in logs:
                if log.correlation_id:
                  corr_key = f"{log.correlation_id}:{log.status}"
                  if corr_key not in visited_corr_cache:
                    visited_corr_cache.add(corr_key)
                    recent_corrs[log.correlation_id] = {
                      "status": log.status,
                      "provider": log.provider,
                      "model": log.model,
                      "latency_ms": log.latency_ms,
                      "cost_usd": log.cost_usd,
                      "created_at": log.created_at.isoformat() if log.created_at else None,
                    }

              # Keep cache bounded
              if len(visited_corr_cache) > 200:
                visited_corr_cache.clear()

              if recent_corrs:
                events.append({
                  "type": "pipeline_runs_updated",
                  "data": {
                    "delta": recent_corrs,
                    "count": len(recent_corrs),
                  }
                })

              # System metrics
              events.append({
                "type": "metrics_updated",
                "data": {
                  "uptime_percent": 99.98,
                  "active_requests": request_count,
                  "llm_cost_usd": llm_cost
                }
              })

              for event in events:
                yield f"data: {json.dumps(event)}\n\n"

            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )