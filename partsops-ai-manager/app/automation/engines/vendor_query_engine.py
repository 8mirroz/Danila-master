"""Vendor query engine — not wired; use my-crawler / supplier tables."""
from __future__ import annotations

from typing import Any


def query_vendor(payload: Any = None) -> dict:
    """Honest not_wired stub for external vendor queries."""
    return {
        "implemented": False,
        "status": "not_wired",
        "reason": "use my-crawler / supplier tables (suppliers.Supplier, SupplierTable)",
        "results": [],
        "ok": False,
        "payload_received": payload is not None,
    }
