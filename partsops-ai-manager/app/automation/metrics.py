"""
Metrics — tenant-scoped counters and KPI snapshots used by jobs and admin API.

All methods accept an existing `session`; they never open a long-lived
transaction themselves — they commit their own changes only when
`commit=True`.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlmodel import Session, select, func

from models import (
    PartRequest,
    RequestEvent,
    ERPSyncLog,
    JobRun,
    RequestScore,
    RequestState,
    EventType,
)


def _now() -> datetime:
    return datetime.utcnow()


def _today_range() -> tuple[datetime, datetime]:
    n = _now()
    start = n.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, n


class AutomationMetrics:
    def __init__(self, session: Session, tenant_id: str = "default"):
        self._session = session
        self._tenant_id = tenant_id

    def counts_by_state(self) -> Dict[str, int]:
        stmt = (
            select(PartRequest.status, func.count(PartRequest.id))
            .where(PartRequest.tenant_id == self._tenant_id)
            .group_by(PartRequest.status)
        )
        return {row[0]: row[1] for row in self._session.exec(stmt).all()}

    def total_requests(self) -> int:
        stmt = select(func.count(PartRequest.id)).where(
            PartRequest.tenant_id == self._tenant_id
        )
        return self._session.exec(stmt).one() or 0

    def events_today(self) -> int:
        start, _ = _today_range()
        stmt = (
            select(func.count(RequestEvent.id))
            .where(RequestEvent.tenant_id == self._tenant_id)
            .where(RequestEvent.occurred_at >= start)
        )
        return self._session.exec(stmt).one() or 0

    def erp_sync_health(self) -> Dict[str, Any]:
        stmt = (
            select(ERPSyncLog.status, func.count(ERPSyncLog.id))
            .where(ERPSyncLog.tenant_id == self._tenant_id)
            .group_by(ERPSyncLog.status)
        )
        return {row[0]: row[1] for row in self._session.exec(stmt).all()}

    def jobs_health(self, since_hours: int = 24) -> Dict[str, Any]:
        cutoff = _now() - __import__("datetime").timedelta(hours=since_hours)
        stmt = (
            select(JobRun.job_name, JobRun.status, func.count(JobRun.id))
            .where(JobRun.tenant_id == self._tenant_id)
            .where(JobRun.created_at >= cutoff)
            .group_by(JobRun.job_name, JobRun.status)
        )
        rows: Dict[str, Dict[str, int]] = {}
        for job_name, status, count in self._session.exec(stmt).all():
            rows.setdefault(job_name, {})[status] = count
        return rows

    def request_scores(self) -> List[Dict[str, Any]]:
        stmt = (
            select(RequestScore)
            .where(RequestScore.tenant_id == self._tenant_id)
            .order_by(RequestScore.id.desc())
        )
        rows = self._session.exec(stmt).all()
        return [
            {
                "request_id": r.request_id,
                "composite_score": r.composite_score,
                "resolved": r.resolved,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    def sla_stats(self) -> Dict[str, Any]:
        """
        Rough per-request age in WAITING_FOR states.

        SLA policy lives in policies/sla_policy.yaml; this is the runtime
        aggregation.
        """
        cutoff = _now() - __import__("datetime").timedelta(hours=2)
        waiting_states = {
            RequestState.READY_FOR_APPROVAL,
            RequestState.NEEDS_CLARIFICATION,
            RequestState.MANUAL_REVIEW,
            RequestState.FINANCE_REVIEW,
            RequestState.ERP_SYNC_FAILED,
            RequestState.SUPPLIER_ISSUE,
            RequestState.RETURN_CASE,
        }
        stmt = (
            select(PartRequest.status, func.count(PartRequest.id))
            .where(PartRequest.tenant_id == self._tenant_id)
            .where(PartRequest.status.in_(waiting_states))
            .where(PartRequest.updated_at < cutoff)
            .group_by(PartRequest.status)
        )
        return {"breached_by_state": {r[0]: r[1] for r in self._session.exec(stmt).all()}}
