"""
Data Health Endpoint — aggregated counts, freshness metrics, health indicators,
and alerts for the admin cockpit data state management.

Provides the backend contract for the frontend's data-state-driven UI:
- Entity counts by status (requests, suppliers, invoices, etc.)
- Freshness timestamps (last event, LLM call, supplier feed, ERP sync)
- Health indicators (queue staleness, approval pressure, ERP/agent/supplier health)
- Auto-generated alerts (stuck requests, failing syncs, stale feeds)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func, desc, col

from database import get_session
from models import (
    PartRequest, RequestEvent, LLMUsageLog,
    ERPSyncLog, ApprovalTicket, JobRun,
)
from rbac import get_privileged_tenant
from suppliers import Supplier, Invoice

router = APIRouter(prefix="/api/admin", tags=["Data Health"])

# ── helpers ──────────────────────────────────────────────────────────

_TERMINAL_STATES = {"CLOSED", "CANCELLED", "FAILED", "EXPIRED", "CLIENT_REJECTED"}

_STALE_QUEUE_HOURS = 24
_STALE_FEED_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dt_or_none(val: Any) -> str | None:
    return val.isoformat() if val else None


def _seconds_since(val: datetime | None) -> float | None:
    if val is None:
        return None
    return (_utcnow() - val).total_seconds()


def _hours_since(val: datetime | None) -> float | None:
    s = _seconds_since(val)
    return round(s / 3600, 1) if s is not None else None


# ── endpoint ─────────────────────────────────────────────────────────

@router.get("/data-health")
def get_data_health(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    now = _utcnow()

    # ── 1. Entity counts ─────────────────────────────────────────

    # Requests by status
    request_rows = session.exec(
        select(PartRequest.status, func.count(col(PartRequest.id)))
        .where(PartRequest.tenant_id == tenant_id)
        .group_by(PartRequest.status)
    ).all()
    requests_by_status: dict[str, int] = {s: c for s, c in request_rows}
    requests_total = sum(requests_by_status.values())
    active_queue_count = sum(
        c for s, c in requests_by_status.items() if s not in _TERMINAL_STATES
    )

    # Suppliers
    supplier_total = session.exec(
        select(func.count(col(Supplier.id)))
        .where(Supplier.tenant_id == tenant_id)
    ).first() or 0
    supplier_active = session.exec(
        select(func.count(col(Supplier.id)))
        .where(Supplier.tenant_id == tenant_id, Supplier.is_active == True)
    ).first() or 0

    # Invoices by status
    invoice_rows = session.exec(
        select(Invoice.status, func.count(col(Invoice.id)))
        .where(Invoice.tenant_id == tenant_id)
        .group_by(Invoice.status)
    ).all()
    invoices_by_status: dict[str, int] = {s: c for s, c in invoice_rows}

    # Approval tickets by status
    ticket_rows = session.exec(
        select(ApprovalTicket.status, func.count(col(ApprovalTicket.id)))
        .where(ApprovalTicket.tenant_id == tenant_id)
        .group_by(ApprovalTicket.status)
    ).all()
    approval_by_status: dict[str, int] = {s: c for s, c in ticket_rows}

    # ERP sync logs by status
    erp_rows = session.exec(
        select(ERPSyncLog.status, func.count(col(ERPSyncLog.id)))
        .where(ERPSyncLog.tenant_id == tenant_id)
        .group_by(ERPSyncLog.status)
    ).all()
    erp_by_status: dict[str, int] = {s: c for s, c in erp_rows}

    # Total events & LLM calls
    events_total = session.exec(
        select(func.count(col(RequestEvent.id)))
        .where(RequestEvent.tenant_id == tenant_id)
    ).first() or 0

    llm_total = session.exec(
        select(func.count(col(LLMUsageLog.id)))
        .where(LLMUsageLog.tenant_id == tenant_id)
    ).first() or 0

    # ── 2. Freshness metrics ────────────────────────────────────

    last_request_created = session.exec(
        select(func.max(PartRequest.created_at))
        .where(PartRequest.tenant_id == tenant_id)
    ).first()

    last_request_updated = session.exec(
        select(func.max(PartRequest.updated_at))
        .where(PartRequest.tenant_id == tenant_id)
    ).first()

    last_event = session.exec(
        select(func.max(RequestEvent.occurred_at))
        .where(RequestEvent.tenant_id == tenant_id)
    ).first()

    last_llm = session.exec(
        select(func.max(LLMUsageLog.created_at))
        .where(LLMUsageLog.tenant_id == tenant_id)
    ).first()

    last_supplier_feed = session.exec(
        select(func.max(Supplier.last_feed_at))
        .where(Supplier.tenant_id == tenant_id)
    ).first()

    last_erp_sync = session.exec(
        select(func.max(ERPSyncLog.last_attempt_at))
        .where(ERPSyncLog.tenant_id == tenant_id)
    ).first()

    # ── 3. Health indicators ────────────────────────────────────

    # Queue staleness: requests stuck in non-terminal states for >24h / >72h
    stuck_24h = 0
    stuck_72h = 0
    oldest_active_hours: float | None = None

    terminal_list = list(_TERMINAL_STATES)
    active_requests = session.exec(
        select(PartRequest.updated_at, PartRequest.created_at)
        .where(PartRequest.tenant_id == tenant_id)
        .where(PartRequest.status.notin_(terminal_list))  # type: ignore[union-attr]
    ).all()

    for updated_at, created_at in active_requests:
        ref_ts = updated_at or created_at
        if ref_ts:
            age_hours = (now - ref_ts).total_seconds() / 3600
            if age_hours >= 72:
                stuck_72h += 1
                stuck_24h += 1
            elif age_hours >= 24:
                stuck_24h += 1
            if oldest_active_hours is None or age_hours > oldest_active_hours:
                oldest_active_hours = round(age_hours, 1)

    # Approval pressure
    pending_approvals = approval_by_status.get("pending", 0)

    # ERP health
    erp_failed_count = erp_by_status.get("FAILED", 0)

    # Agent (LLM) health: error rate in last hour
    one_hour_ago_dt = now - timedelta(hours=1)
    llm_last_hour = session.exec(
        select(func.count(col(LLMUsageLog.id)))
        .where(LLMUsageLog.tenant_id == tenant_id)
        .where(col(LLMUsageLog.created_at) >= one_hour_ago_dt)
    ).first() or 0

    llm_errors_last_hour = session.exec(
        select(func.count(col(LLMUsageLog.id)))
        .where(LLMUsageLog.tenant_id == tenant_id)
        .where(col(LLMUsageLog.created_at) >= one_hour_ago_dt)
        .where(LLMUsageLog.status == "error")
    ).first() or 0

    llm_error_rate = round(llm_errors_last_hour / llm_last_hour, 4) if llm_last_hour else 0.0

    # Supplier feed freshness
    feed_cutoff_dt = now - timedelta(days=_STALE_FEED_DAYS)
    stale_feed_suppliers = session.exec(
        select(func.count(col(Supplier.id)))
        .where(Supplier.tenant_id == tenant_id)
        .where(col(Supplier.last_feed_at) < feed_cutoff_dt)
    ).first() or 0

    no_feed_suppliers = session.exec(
        select(func.count(col(Supplier.id)))
        .where(Supplier.tenant_id == tenant_id)
        .where(col(Supplier.last_feed_at).is_(None))
    ).first() or 0

    # ── 4. Alerts ───────────────────────────────────────────────

    alerts: list[dict[str, Any]] = []

    if stuck_24h > 0:
        alerts.append({
            "level": "warning" if stuck_24h <= 5 else "critical",
            "source": "queue_staleness",
            "message": f"{stuck_24h} заявок не обновлялось более 24ч",
            "count": stuck_24h,
        })

    if pending_approvals > 0:
        alerts.append({
            "level": "info" if pending_approvals <= 3 else "warning",
            "source": "approval_pressure",
            "message": f"{pending_approvals} ожидают согласования",
            "count": pending_approvals,
        })

    if erp_failed_count > 0:
        alerts.append({
            "level": "warning" if erp_failed_count <= 3 else "critical",
            "source": "erp_sync",
            "message": f"{erp_failed_count} ERP синхронизаций в статусе FAILED",
            "count": erp_failed_count,
        })

    if stale_feed_suppliers > 0:
        alerts.append({
            "level": "info",
            "source": "supplier_feed",
            "message": f"{stale_feed_suppliers} поставщиков не обновляли фид >{_STALE_FEED_DAYS} дней",
            "count": stale_feed_suppliers,
        })

    if llm_errors_last_hour > 0:
        alerts.append({
            "level": "warning",
            "source": "agent_health",
            "message": f"{llm_errors_last_hour} ошибок LLM за последний час",
            "count": llm_errors_last_hour,
        })

    # ── Response ────────────────────────────────────────────────

    return {
        "status": "ok",
        "generated_at": now.isoformat(),
        "tenant_id": tenant_id,

        "entity_counts": {
            "requests": {
                "total": requests_total,
                "by_status": requests_by_status,
                "active_queue_total": active_queue_count,
            },
            "suppliers": {
                "total": supplier_total,
                "active": supplier_active,
                "inactive": supplier_total - supplier_active,
            },
            "invoices": {
                "total": sum(invoices_by_status.values()),
                "by_status": invoices_by_status,
            },
            "approval_tickets": {
                "total": sum(approval_by_status.values()),
                "by_status": approval_by_status,
            },
            "erp_sync_logs": {
                "total": sum(erp_by_status.values()),
                "by_status": erp_by_status,
            },
            "events": {
                "total": events_total,
            },
            "llm_usage_logs": {
                "total": llm_total,
            },
        },

        "freshness": {
            "last_request_created": _dt_or_none(last_request_created),
            "last_request_updated": _dt_or_none(last_request_updated),
            "last_event_recorded": _dt_or_none(last_event),
            "last_llm_call": _dt_or_none(last_llm),
            "last_supplier_feed": _dt_or_none(last_supplier_feed),
            "last_erp_sync": _dt_or_none(last_erp_sync),
            "seconds_since_last_event": _seconds_since(last_event),
            "seconds_since_last_llm_call": _seconds_since(last_llm),
        },

        "health_indicators": {
            "queue_staleness": {
                "stuck_over_24h": stuck_24h,
                "stuck_over_72h": stuck_72h,
                "oldest_active_request_hours": oldest_active_hours,
            },
            "approval_pressure": {
                "pending_approvals": pending_approvals,
            },
            "erp_health": {
                "currently_failing": erp_failed_count,
            },
            "agent_health": {
                "llm_error_rate_last_hour": llm_error_rate,
                "llm_errors_last_hour": llm_errors_last_hour,
                "llm_requests_last_hour": llm_last_hour,
            },
            "supplier_feed_freshness": {
                "feed_stale_suppliers": stale_feed_suppliers,
                "suppliers_without_feed": no_feed_suppliers,
            },
        },

        "alerts": alerts,
    }
