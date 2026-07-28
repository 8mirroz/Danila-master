"""Quote score engine — thin wrapper over quote_evaluation_engine.score_quotes."""
from __future__ import annotations

from typing import Any


def score_quotes(quotes: Any) -> dict:
    """Alias / wrapper for quote evaluation ranking."""
    from app.automation.engines.quote_evaluation_engine import score_quotes as _score

    return _score(quotes)


# Backward-compatible name some callers may expect
def score(quotes: Any) -> dict:
    return score_quotes(quotes)
