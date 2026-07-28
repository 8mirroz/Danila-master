"""Purchase order generation engine — local draft only (not ERP)."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

logger = logging.getLogger(__name__)


def generate_po(data: Any) -> dict:
    """
    Generate a local PO draft identifier.

    Does not send to ERP or external procurement systems.
    """
    payload: Dict[str, Any] = data if isinstance(data, dict) else {}
    po_number = f"PO-{uuid.uuid4().hex[:12].upper()}"

    logger.info(
        "generate_po local draft only: po_number=%s request_id=%s",
        po_number,
        payload.get("request_id"),
    )

    return {
        "implemented": True,
        "status": "partial",
        "reason": "local_draft_only_not_sent_to_erp",
        "po_number": po_number,
        "ok": True,
        "request_id": payload.get("request_id"),
        "tenant_id": payload.get("tenant_id"),
    }
