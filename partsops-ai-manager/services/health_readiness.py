"""Liveness vs readiness probes (no secrets).

- collect_liveness: process + DB only — safe for k8s liveness/load balancers.
- collect_readiness: storage + ERP (cached) + worker expectation + LLM budget.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

_ERP_CACHE_LOCK = threading.Lock()
_ERP_CACHE: Optional[Tuple[float, Dict[str, Any]]] = None
_ERP_CACHE_TTL = float(os.environ.get("PARTSOPS_ERP_HEALTH_CACHE_TTL", "30"))


def collect_liveness() -> Dict[str, Any]:
    """Lightweight probe: DB connectivity only."""
    checks: Dict[str, Any] = {}
    try:
        from sqlalchemy import text
        from database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
        overall = "healthy"
    except Exception as exc:
        checks["database"] = {"status": "error", "reason": str(exc)[:200]}
        overall = "unhealthy"
    return {"status": overall, "checks": checks}


def _erp_health_cached() -> Dict[str, Any]:
    global _ERP_CACHE
    now = time.time()
    with _ERP_CACHE_LOCK:
        if _ERP_CACHE is not None:
            ts, payload = _ERP_CACHE
            if now - ts < _ERP_CACHE_TTL:
                return dict(payload)

    try:
        from erp_adapter import check_erpnext_connection

        erp = check_erpnext_connection()
        payload = {
            "status": erp.get("status", "unknown"),
            "dry_run": erp.get("dry_run"),
            "cached": False,
        }
    except Exception as exc:
        payload = {"status": "error", "reason": str(exc)[:120], "cached": False}

    with _ERP_CACHE_LOCK:
        _ERP_CACHE = (now, {**payload, "cached": True})
    return payload


def collect_readiness(*, include_erp: bool = True) -> Dict[str, Any]:
    """Full readiness map for /health/ready (never raises)."""
    checks: Dict[str, Any] = {}

    live = collect_liveness()
    checks["database"] = live["checks"].get("database", {"status": "unknown"})

    storage_backend = (os.environ.get("PARTSOPS_STORAGE_BACKEND") or "local").lower()
    if storage_backend in {"s3", "minio"}:
        bucket = bool(os.environ.get("S3_BUCKET") or os.environ.get("AWS_S3_BUCKET"))
        checks["storage"] = {
            "status": "ok" if bucket else "not_configured",
            "backend": storage_backend,
        }
    else:
        checks["storage"] = {"status": "ok", "backend": "local"}

    if include_erp:
        checks["erp"] = _erp_health_cached()
    else:
        checks["erp"] = {"status": "skipped"}

    checks["pipeline_worker"] = {
        "status": "optional",
        "expected": os.environ.get("PARTSOPS_START_PIPELINE_WORKER", "1") == "1",
        "note": "Worker process is external; presence not verified from API process",
    }

    try:
        from budget_guard import budget_guard

        stats = budget_guard.get_usage_stats()  # all models when model=None (DB SoT)
        checks["llm_budget"] = {
            "status": "ok",
            "hourly_tokens_used": stats.get("hourly_tokens_used"),
            "daily_cost_usd": stats.get("daily_cost_usd"),
            "source": stats.get("source"),
        }
    except Exception as exc:
        checks["llm_budget"] = {"status": "error", "reason": str(exc)[:120]}

    overall = "healthy"
    if checks.get("database", {}).get("status") == "error":
        overall = "unhealthy"
    else:
        for key, val in checks.items():
            if key == "pipeline_worker":
                continue
            if (val or {}).get("status") == "error":
                overall = "degraded"
                break

    return {"status": overall, "checks": checks}
