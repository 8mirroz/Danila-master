"""Multi-channel notification engine."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

def notify(recipient, message) -> dict:
    logger.info("notify called")
    return {"ok": True, "sent": False}
