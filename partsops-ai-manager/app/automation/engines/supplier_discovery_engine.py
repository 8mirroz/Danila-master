"""Supplier discovery engine — DB-backed when session provided."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def find_suppliers(ctx: Any) -> dict:
    """
    Discover active suppliers.

    With session: query Supplier model (limit 50, optional specialization filter).
    Without session: not_wired with empty list.
    """
    if ctx is None:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "missing_ctx_session; pass session + tenant_id",
            "suppliers": [],
            "ok": False,
        }

    data: Dict[str, Any]
    session = None
    if isinstance(ctx, dict):
        data = ctx
        session = data.get("session")
    else:
        # duck-typed AutomationContext-like
        data = {
            "tenant_id": getattr(ctx, "tenant_id", "default"),
            "specialization": getattr(ctx, "specialization", None),
            "payload": getattr(ctx, "payload", None) or {},
        }
        session = getattr(ctx, "session", None)
        if session is None and isinstance(data.get("payload"), dict):
            session = data["payload"].get("session")

    if session is None:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "missing_session; query Supplier via suppliers.Supplier / jobs",
            "suppliers": [],
            "ok": False,
        }

    tenant_id = data.get("tenant_id") or "default"
    specialization: Optional[str] = data.get("specialization")
    if specialization is None and isinstance(data.get("payload"), dict):
        specialization = data["payload"].get("specialization")

    try:
        from sqlmodel import select
        from suppliers import Supplier
    except Exception as exc:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": f"supplier_model_unavailable:{exc}",
            "suppliers": [],
            "ok": False,
        }

    try:
        query = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.is_active == True,  # noqa: E712
        )
        # prefer status=active when present
        try:
            query = query.where(Supplier.status == "active")
        except Exception:
            pass

        rows = session.exec(query.limit(50)).all()
        suppliers: List[Dict[str, Any]] = []
        for row in rows:
            spec = getattr(row, "specialization", "") or ""
            if specialization:
                needle = str(specialization).lower()
                if needle not in spec.lower():
                    continue
            suppliers.append(
                {
                    "supplier_id": getattr(row, "supplier_id", None),
                    "name": getattr(row, "name", None),
                    "specialization": spec,
                    "reliability_score": getattr(row, "reliability_score", None),
                    "city": getattr(row, "city", None),
                    "is_active": getattr(row, "is_active", True),
                }
            )

        return {
            "implemented": True,
            "status": "ok",
            "reason": None,
            "suppliers": suppliers,
            "ok": True,
            "count": len(suppliers),
            "tenant_id": tenant_id,
        }
    except Exception as exc:
        logger.exception("find_suppliers failed")
        return {
            "implemented": True,
            "status": "error",
            "reason": str(exc),
            "suppliers": [],
            "ok": False,
        }
