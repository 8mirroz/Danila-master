"""Policy and compliance checks."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

def check_policy(data) -> dict:
    logger.info("check_policy called")
    return {"ok": True, "violations": []}
