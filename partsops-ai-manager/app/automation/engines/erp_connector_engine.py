"""ERP sync/retry engine — thin adapter over erp_adapter when wired."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def sync_erp(record: Any) -> dict:
    """
    Attempt ERP invoice-draft sync when request_id + session are available.

    Never reports silent success when nothing was attempted.
    """
    data: Dict[str, Any] = record if isinstance(record, dict) else {}
    request_id = data.get("request_id")
    tenant_id = data.get("tenant_id") or "default"
    session = data.get("session")
    dry_run = data.get("dry_run")
    if dry_run is None:
        dry_run_env = os.getenv("ERP_DRY_RUN")
        if dry_run_env is not None:
            dry_run = dry_run_env == "1"
        else:
            dry_run = None  # let erp_adapter default

    if not request_id or session is None:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "missing_request_id_or_session; use erp_adapter.sync_invoice_draft / erp_sync_job",
            "synced": False,
            "ok": False,
        }

    try:
        from erp_adapter import sync_invoice_draft
    except Exception as exc:
        logger.warning("erp_adapter import failed: %s", exc)
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": f"erp_adapter_unavailable:{exc}; use erp_adapter / erp_sync_job",
            "synced": False,
            "ok": False,
        }

    try:
        result = sync_invoice_draft(
            request_id=str(request_id),
            session=session,
            tenant_id=str(tenant_id),
            dry_run=dry_run,
        )
    except Exception as exc:
        logger.exception("sync_invoice_draft failed for %s", request_id)
        return {
            "implemented": True,
            "status": "error",
            "reason": str(exc),
            "synced": False,
            "ok": False,
            "request_id": request_id,
        }

    result_status = (result or {}).get("status") or ""
    # erp_adapter uses SUCCESS / DRY_RUN / ERROR style statuses
    upper = str(result_status).upper()
    if upper in ("SUCCESS", "OK", "DRY_RUN", "PENDING"):
        synced = upper != "PENDING" or bool((result or {}).get("synced"))
        # dry-run still "attempted" honestly
        return {
            "implemented": True,
            "status": "ok" if upper in ("SUCCESS", "OK", "DRY_RUN") else "partial",
            "reason": (result or {}).get("reason"),
            "synced": upper in ("SUCCESS", "OK") or (
                upper == "DRY_RUN" and bool((result or {}).get("dry_run", True))
            ),
            "ok": True,
            "request_id": request_id,
            "erp_result": result,
            "dry_run": (result or {}).get("dry_run", dry_run),
        }

    return {
        "implemented": True,
        "status": "error" if upper in ("ERROR", "FAILED") else "partial",
        "reason": (result or {}).get("reason") or f"erp_status:{result_status}",
        "synced": False,
        "ok": False,
        "request_id": request_id,
        "erp_result": result,
    }
