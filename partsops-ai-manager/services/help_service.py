"""
PartsOps AI Manager v3 — Help Corpus Service.
Deterministic retrieval of help sources for Hermes Copilot.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional, Dict, Any

HELP_CORPUS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "01_CONFIGS",
    "help_corpus.json"
)

_cached_corpus: Optional[List[Dict[str, Any]]] = None


def load_help_corpus() -> List[Dict[str, Any]]:
    global _cached_corpus
    if _cached_corpus is not None:
        return _cached_corpus

    if os.path.exists(HELP_CORPUS_PATH):
        try:
            with open(HELP_CORPUS_PATH, "r", encoding="utf-8") as f:
                _cached_corpus = json.load(f)
                return _cached_corpus
        except Exception:
            pass
    _cached_corpus = []
    return _cached_corpus


def get_help_sources_for_context(
    screen_id: str,
    user_role: str = "manager",
    query: Optional[str] = None,
    limit: int = 3
) -> List[Dict[str, Any]]:
    corpus = load_help_corpus()
    matched = []

    for article in corpus:
        # Check role permission
        if user_role not in article.get("roles", []):
            continue

        score = 0
        if screen_id in article.get("screen_ids", []):
            score += 10

        if query:
            q_lower = query.lower()
            if q_lower in article.get("title", "").lower():
                score += 5
            if any(tag in q_lower for tag in article.get("tags", [])):
                score += 3
            if q_lower in article.get("content", "").lower():
                score += 2

        if score > 0 or not query:
            matched.append((score, article))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in matched[:limit]]


def get_help_source_by_id(source_id: str) -> Optional[Dict[str, Any]]:
    corpus = load_help_corpus()
    for article in corpus:
        if article.get("source_id") == source_id:
            return article
    return None
