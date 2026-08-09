"""Vendor query engine — DB catalog / supplier table lookup (no silent empty success).

Live Playwright scraping stays in my-crawler / live_scraper_service; this engine
is the synchronous automation adapter for catalog-backed vendor offers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def query_vendor(payload: Any = None) -> dict:
    """
    Query vendor/catalog offers for an article or free-text part name.

    Expected payload keys (dict):
      - session: SQLModel session (required for implemented path)
      - tenant_id: str (default "default")
      - article / oem / query / part_name: search string
      - limit: max results (default 10)
      - threshold: matcher score floor (default 50)

    Without session or query → not_wired / partial with honest reason.
    """
    data: Dict[str, Any] = payload if isinstance(payload, dict) else {}
    session = data.get("session")
    tenant_id = str(data.get("tenant_id") or "default")
    query = (
        data.get("article")
        or data.get("oem")
        or data.get("query")
        or data.get("part_name")
        or data.get("oem_number")
        or ""
    )
    query = str(query).strip()
    try:
        limit = int(data.get("limit") or 10)
    except (TypeError, ValueError):
        limit = 10
    try:
        threshold = float(data.get("threshold") if data.get("threshold") is not None else 50.0)
    except (TypeError, ValueError):
        threshold = 50.0

    if not query:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "missing_query; pass article/oem/query/part_name",
            "results": [],
            "ok": False,
            "payload_received": payload is not None,
        }

    if session is None:
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": "missing_session; pass session + tenant_id for catalog lookup "
            "(live scrape: live_scraper_service / my-crawler)",
            "results": [],
            "ok": False,
            "query": query,
            "payload_received": True,
        }

    try:
        from matcher import match_part_from_db
    except Exception as exc:
        logger.warning("matcher unavailable for vendor_query: %s", exc)
        return {
            "implemented": False,
            "status": "not_wired",
            "reason": f"matcher_unavailable:{exc}",
            "results": [],
            "ok": False,
            "query": query,
        }

    vehicle_ctx = data.get("vehicle_context") or data.get("vehicle_make")
    if isinstance(vehicle_ctx, str) and vehicle_ctx.strip():
        vehicle_context: Optional[List[str]] = [vehicle_ctx.strip()]
    elif isinstance(vehicle_ctx, list):
        vehicle_context = [str(v) for v in vehicle_ctx if v]
    else:
        vehicle_context = None

    try:
        matches = match_part_from_db(
            query,
            session,
            threshold=threshold,
            limit=limit,
            vehicle_context=vehicle_context,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.exception("vendor_query match failed for %s", query)
        return {
            "implemented": True,
            "status": "error",
            "reason": str(exc),
            "results": [],
            "ok": False,
            "query": query,
            "tenant_id": tenant_id,
        }

    results: List[Dict[str, Any]] = []
    for m in matches or []:
        item = m.get("item") if isinstance(m, dict) else None
        supplier = m.get("supplier") if isinstance(m, dict) else None
        results.append(
            {
                "score": m.get("score") if isinstance(m, dict) else None,
                "breakdown": m.get("breakdown") if isinstance(m, dict) else None,
                "item": item,
                "supplier": supplier,
                "source": "supplier_catalog",
            }
        )

    if not results:
        return {
            "implemented": True,
            "status": "partial",
            "reason": "no_catalog_matches",
            "results": [],
            "ok": True,
            "query": query,
            "tenant_id": tenant_id,
            "source": "supplier_catalog",
        }

    return {
        "implemented": True,
        "status": "ok",
        "reason": None,
        "results": results,
        "ok": True,
        "query": query,
        "tenant_id": tenant_id,
        "count": len(results),
        "source": "supplier_catalog",
    }
