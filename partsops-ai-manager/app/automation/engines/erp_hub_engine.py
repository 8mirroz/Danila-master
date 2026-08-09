"""ERP hub engine — thin router over erp_connector when session+request_id present."""
from __future__ import annotations

from typing import Any, Dict


def route_erp(payload: Any = None) -> dict:
    """
    Route ERP work through erp_connector_engine.sync_erp when wired.

    Without request_id + session: not_wired (point callers to erp_sync_job).
    With both: delegates to sync_erp and reports routed=True when adapter ran.
    """
    data: Dict[str, Any] = payload if isinstance(payload, dict) else {}
    request_id = data.get("request_id")
    session = data.get("session")

    if not request_id or session is None:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "missing_request_id_or_session; use erp_adapter.sync_invoice_draft / erp_sync_job",
            "routed": False,
            "ok": False,
            "payload_received": payload is not None,
        }

    from app.automation.engines.erp_connector_engine import sync_erp

    result = sync_erp(data)
    routed = bool(result.get("implemented"))
    return {
        "implemented": result.get("implemented", False),
        "status": result.get("status", "error"),
        "reason": result.get("reason"),
        "routed": routed and result.get("status") in {"ok", "partial", "error"},
        "ok": bool(result.get("ok")),
        "synced": result.get("synced", False),
        "request_id": request_id,
        "erp_result": result,
    }
