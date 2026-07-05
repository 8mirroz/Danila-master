"""VIN decoding engine."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

def decode_vin(vin: str) -> dict:
    logger.info("decode_vin called")
    return {"vin": vin, "decoded": False, "reason": "stub"}
