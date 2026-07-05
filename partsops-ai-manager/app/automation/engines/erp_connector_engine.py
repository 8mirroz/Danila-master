"""ERP sync/retry engine."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

def sync_erp(record) -> dict:
    logger.info("sync_erp called")
    return {"ok": True, "synced": False}
