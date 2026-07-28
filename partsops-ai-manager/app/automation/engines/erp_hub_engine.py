"""ERP hub engine — routing not wired; use erp_adapter / erp_sync_job."""
from __future__ import annotations

from typing import Any


def route_erp(payload: Any = None) -> dict:
    """Honest not_wired stub for ERP routing hub (Phase 4)."""
    return {
        "implemented": False,
        "status": "not_wired",
        "reason": "use erp_adapter.sync_invoice_draft / app.automation.jobs.erp_sync_job",
        "routed": False,
        "ok": False,
        "payload_received": payload is not None,
    }
