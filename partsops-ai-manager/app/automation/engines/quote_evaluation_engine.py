"""Quote scoring and evaluation engine — local ranking only."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def score_quotes(quotes: Any) -> dict:
    """
    Rank quotes by highest score if present, else lowest price/total.

    Pure local evaluation; does not contact suppliers or ERP.
    """
    if quotes is None:
        quotes_list: List[Any] = []
    elif isinstance(quotes, list):
        quotes_list = quotes
    else:
        quotes_list = list(quotes) if quotes else []

    if not quotes_list:
        return {
            "implemented": True,
            "status": "partial",
            "reason": "empty_quotes",
            "best_quote": None,
            "scores": [],
            "ok": True,
        }

    scores: List[Dict[str, Any]] = []
    use_score = any(
        isinstance(q, dict) and q.get("score") is not None for q in quotes_list
    )

    for idx, q in enumerate(quotes_list):
        if not isinstance(q, dict):
            scores.append(
                {
                    "index": idx,
                    "quote": q,
                    "rank_key": None,
                    "error": "not_a_dict",
                }
            )
            continue

        price = q.get("price", q.get("total"))
        score_val = q.get("score")
        entry: Dict[str, Any] = {
            "index": idx,
            "quote": q,
            "price": price,
            "score": score_val,
        }
        if use_score and score_val is not None:
            try:
                entry["rank_key"] = float(score_val)
                entry["rank_mode"] = "score_desc"
            except (TypeError, ValueError):
                entry["rank_key"] = None
                entry["rank_mode"] = "score_desc"
        else:
            try:
                entry["rank_key"] = float(price) if price is not None else None
                entry["rank_mode"] = "price_asc"
            except (TypeError, ValueError):
                entry["rank_key"] = None
                entry["rank_mode"] = "price_asc"
        scores.append(entry)

    ranked = [s for s in scores if s.get("rank_key") is not None]
    if not ranked:
        return {
            "implemented": True,
            "status": "partial",
            "reason": "no_rankable_quotes",
            "best_quote": None,
            "scores": scores,
            "ok": True,
        }

    reverse = ranked[0].get("rank_mode") == "score_desc"
    ranked.sort(key=lambda s: s["rank_key"], reverse=reverse)
    best = ranked[0]["quote"]

    # annotate ranks
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    return {
        "implemented": True,
        "status": "ok",
        "reason": None,
        "best_quote": best,
        "scores": scores,
        "ok": True,
        "rank_mode": "score_desc" if reverse else "price_asc",
    }
