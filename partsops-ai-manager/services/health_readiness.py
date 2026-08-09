"""Readiness probes for /health — storage, ERP, worker, LLM budget (no secrets)."""
from __future__ import annotations

import os
from typing import Any, Dict


def collect_readiness() -> Dict[str, Any]:
    """Best-effort readiness map; never raises."""
    checks: Dict[str, Any] = {}

    # Database
    try:
        from sqlalchemy import text
        from database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        checks["database"] = {"status": "error", "reason": str(exc)[:200]}

    # Storage backend
    storage_backend = (os.environ.get("PARTSOPS_STORAGE_BACKEND") or "local").lower()
    if storage_backend in {"s3", "minio"}:
        bucket = bool(os.environ.get("S3_BUCKET") or os.environ.get("AWS_S3_BUCKET"))
        checks["storage"] = {
            "status": "ok" if bucket else "not_configured",
            "backend": storage_backend,
        }
    else:
        checks["storage"] = {"status": "ok", "backend": "local"}

    # ERP connector (read-only preflight — never returns credentials)
    try:
        from erp_adapter import check_erpnext_connection

        erp = check_erpnext_connection()
        checks["erp"] = {
            "status": erp.get("status", "unknown"),
            "dry_run": erp.get("dry_run"),
        }
    except Exception as exc:
        checks["erp"] = {"status": "error", "reason": str(exc)[:120]}

    # Pipeline worker expectation (process is external)
    checks["pipeline_worker"] = {
        "status": "optional",
        "expected": os.environ.get("PARTSOPS_START_PIPELINE_WORKER", "1") == "1",
        "note": "Worker process is external; presence not verified from API process",
    }

    # LLM budget snapshot
    try:
        from budget_guard import budget_guard

        stats = budget_guard.get_usage_stats()
        checks["llm_budget"] = {
            "status": "ok",
            "hourly_tokens_used": stats.get("hourly_tokens_used"),
            "daily_cost_usd": stats.get("daily_cost_usd"),
        }
    except Exception as exc:
        checks["llm_budget"] = {"status": "error", "reason": str(exc)[:120]}

    overall = "healthy"
    if checks.get("database", {}).get("status") == "error":
        overall = "unhealthy"
    else:
        for key, val in checks.items():
            if (val or {}).get("status") == "error":
                overall = "degraded"
                break

    return {"status": overall, "checks": checks}
