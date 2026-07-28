"""Decision engine — simple score/threshold approve vs review."""
from __future__ import annotations

from typing import Any, Dict


def decide(payload: Any) -> dict:
    """
    Rule: approve if score >= threshold (default 70) and not blocked; else review.
    """
    data: Dict[str, Any] = payload if isinstance(payload, dict) else {}
    try:
        score = float(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0.0

    try:
        threshold = float(data.get("threshold", 70))
    except (TypeError, ValueError):
        threshold = 70.0

    blocked = bool(data.get("blocked", False))

    if score >= threshold and not blocked:
        decision = "approve"
    else:
        decision = "review"

    return {
        "implemented": True,
        "status": "ok",
        "reason": None,
        "decision": decision,
        "score": score,
        "threshold": threshold,
        "blocked": blocked,
        "ok": True,
    }
