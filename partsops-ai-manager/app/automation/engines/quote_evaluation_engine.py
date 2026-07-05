"""Quote scoring and evaluation engine."""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

def score_quotes(quotes) -> dict:
    logger.info("score_quotes called")
    return {"best_quote": None, "scores": []}
