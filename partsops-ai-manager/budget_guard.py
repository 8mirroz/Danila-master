"""
PartsOps AI Manager v3 — Budget Guard

Multi-worker honesty:
- Usage is keyed by canonical family (normalize_budget_key).
- When DB is available, LLMUsageLog is source of truth for checks/stats.
- In-memory ring is fallback when DB is down.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    model_name: str
    token_budget_per_hour: int
    cost_budget_per_day_usd: float


@dataclass
class UsageRecord:
    timestamp: datetime
    model: str  # canonical budget key
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float = 0.0
    concrete_model: str = ""


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_budget_key(model: str) -> str:
    """
    Map provider concrete model names / aliases to a budget family key.

    Examples:
      meta/llama-3.1-8b-instruct -> family:fast
      meta-llama/llama-3.2-3b-instruct:free -> family:fast
      mistralai/mistral-large-... -> family:default
    """
    if not model:
        return "family:other"
    raw = str(model).strip()
    m = raw.lower().replace("_", "-")
    # Strip openrouter :free / quant suffixes for matching
    m = re.sub(r":.*$", "", m)

    alias_map = {
        "default": "family:default",
        "fast": "family:fast",
        "classify": "family:fast",
        "spam": "family:fast",
        "reasoning": "family:default",
        "low": "family:fast",
    }
    if m in alias_map:
        return alias_map[m]

    # Size / role heuristics
    if any(x in m for x in ("3b", "8b", "mini", "tiny", "nano", "haiku")):
        return "family:fast"
    if any(x in m for x in ("70b", "120b", "405b", "large", "reason", "r1", "opus", "sonnet")):
        return "family:default"
    if "mock" in m:
        return "family:fast"
    return "family:other"


class BudgetGuard:
    DEFAULT_CONFIGS = {
        "family:default": BudgetConfig(
            model_name="family:default",
            token_budget_per_hour=int(os.environ.get("PARTSOPS_LLM_TOKEN_BUDGET_HOUR", "150000")),
            cost_budget_per_day_usd=float(os.environ.get("PARTSOPS_LLM_COST_BUDGET_DAY", "15.0")),
        ),
        "family:fast": BudgetConfig(
            model_name="family:fast",
            token_budget_per_hour=int(os.environ.get("PARTSOPS_LLM_FAST_TOKEN_BUDGET_HOUR", "300000")),
            cost_budget_per_day_usd=float(os.environ.get("PARTSOPS_LLM_FAST_COST_BUDGET_DAY", "8.0")),
        ),
        "family:other": BudgetConfig(
            model_name="family:other",
            token_budget_per_hour=int(os.environ.get("PARTSOPS_LLM_OTHER_TOKEN_BUDGET_HOUR", "100000")),
            cost_budget_per_day_usd=float(os.environ.get("PARTSOPS_LLM_OTHER_COST_BUDGET_DAY", "10.0")),
        ),
        # Back-compat exact names still map via normalize; keep legacy entries
        "meta/llama-3.1-70b-instruct": BudgetConfig(
            model_name="meta/llama-3.1-70b-instruct",
            token_budget_per_hour=100_000,
            cost_budget_per_day_usd=10.0,
        ),
        "meta/llama-3.1-8b-instruct": BudgetConfig(
            model_name="meta/llama-3.1-8b-instruct",
            token_budget_per_hour=200_000,
            cost_budget_per_day_usd=5.0,
        ),
    }

    def __init__(self) -> None:
        self._usage_log: list[UsageRecord] = []
        self._lock = threading.Lock()
        self._configs: Dict[str, BudgetConfig] = dict(self.DEFAULT_CONFIGS)
        self._db_enabled = os.environ.get("PARTSOPS_BUDGET_USE_DB", "1") not in {
            "0",
            "false",
            "no",
        }

    def register_config(self, config: BudgetConfig) -> None:
        self._configs[config.model_name] = config

    def _config_for(self, model: str) -> BudgetConfig:
        key = normalize_budget_key(model)
        if model in self._configs:
            return self._configs[model]
        if key in self._configs:
            return self._configs[key]
        return self._configs["family:other"]

    def _load_db_usage(
        self,
        budget_key: str,
        hour_ago: datetime,
        day_ago: datetime,
        *,
        all_models: bool = False,
    ) -> tuple[int, float, bool]:
        """Return (hour_tokens, day_cost, db_ok)."""
        if not self._db_enabled:
            return 0, 0.0, False
        try:
            from sqlmodel import Session, select
            from database import engine
            from models import LLMUsageLog
        except Exception as exc:  # pragma: no cover
            logger.debug("budget DB import failed: %s", exc)
            return 0, 0.0, False

        try:
            with Session(engine) as session:
                hour_rows = session.exec(
                    select(LLMUsageLog).where(
                        LLMUsageLog.created_at >= hour_ago,
                        LLMUsageLog.status == "ok",
                    )
                ).all()
                day_rows = session.exec(
                    select(LLMUsageLog).where(
                        LLMUsageLog.created_at >= day_ago,
                        LLMUsageLog.status == "ok",
                    )
                ).all()

            def _match(row_model: str) -> bool:
                if all_models:
                    return True
                return normalize_budget_key(row_model or "") == budget_key

            hour_tokens = sum(int(r.total_tokens or 0) for r in hour_rows if _match(r.model))
            day_cost = sum(float(r.cost_usd or 0.0) for r in day_rows if _match(r.model))
            return hour_tokens, day_cost, True
        except Exception as exc:
            logger.debug("budget DB query failed (using memory only): %s", exc)
            return 0, 0.0, False

    def check_budget(self, model: str, tokens: int) -> Dict[str, bool | str]:
        config = self._config_for(model)
        budget_key = normalize_budget_key(model)

        now = _utcnow_naive()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        db_hour, db_day_cost, db_ok = self._load_db_usage(budget_key, hour_ago, day_ago)

        with self._lock:
            mem_hour = sum(
                r.total_tokens
                for r in self._usage_log
                if r.model == budget_key and r.timestamp >= hour_ago
            )
            mem_day = sum(
                r.cost_usd
                for r in self._usage_log
                if r.model == budget_key and r.timestamp >= day_ago
            )

        # DB is SoT when available; memory only as fallback
        if db_ok:
            hour_tokens, day_cost, source = db_hour, db_day_cost, "db"
        else:
            hour_tokens, day_cost, source = mem_hour, mem_day, "memory"

        if hour_tokens + tokens > config.token_budget_per_hour:
            return {
                "allowed": False,
                "reason": (
                    f"hourly token limit exceeded: {hour_tokens}/"
                    f"{config.token_budget_per_hour}"
                ),
                "budget_key": budget_key,
                "source": source,
            }

        estimated_cost = (tokens / 1000) * 0.002
        if day_cost + estimated_cost > config.cost_budget_per_day_usd:
            return {
                "allowed": False,
                "reason": (
                    f"daily cost limit exceeded: ${day_cost:.2f}/"
                    f"${config.cost_budget_per_day_usd}"
                ),
                "budget_key": budget_key,
                "source": source,
            }

        return {
            "allowed": True,
            "reason": "within budget",
            "hourly_tokens_used": hour_tokens,
            "daily_cost_usd": day_cost,
            "budget_key": budget_key,
            "source": source,
        }

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
    ) -> None:
        budget_key = normalize_budget_key(model)
        record = UsageRecord(
            timestamp=_utcnow_naive(),
            model=budget_key,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            concrete_model=str(model or ""),
        )
        with self._lock:
            self._usage_log.append(record)
            if len(self._usage_log) > 5000:
                cutoff = _utcnow_naive() - timedelta(hours=6)
                self._usage_log = [r for r in self._usage_log if r.timestamp >= cutoff]

    def get_usage_stats(self, model: Optional[str] = None) -> Dict:
        now = _utcnow_naive()
        day_ago = now - timedelta(days=1)
        hour_ago = now - timedelta(hours=1)

        if model:
            key = normalize_budget_key(model)
            db_hour, db_day, db_ok = self._load_db_usage(key, hour_ago, day_ago)
            with self._lock:
                mem_hour = sum(
                    r.total_tokens
                    for r in self._usage_log
                    if r.model == key and r.timestamp >= hour_ago
                )
                mem_day = sum(
                    r.cost_usd for r in self._usage_log if r.model == key and r.timestamp >= day_ago
                )
            if db_ok:
                return {
                    "hourly_tokens_used": db_hour,
                    "daily_cost_usd": db_day,
                    "budget_key": key,
                    "source": "db",
                }
            return {
                "hourly_tokens_used": mem_hour,
                "daily_cost_usd": mem_day,
                "budget_key": key,
                "source": "memory",
            }

        # All models
        db_hour, db_day, db_ok = self._load_db_usage("", hour_ago, day_ago, all_models=True)
        with self._lock:
            mem_hour = sum(r.total_tokens for r in self._usage_log if r.timestamp >= hour_ago)
            mem_day = sum(r.cost_usd for r in self._usage_log if r.timestamp >= day_ago)
        if db_ok:
            return {
                "hourly_tokens_used": db_hour,
                "daily_cost_usd": db_day,
                "source": "db",
            }
        return {
            "hourly_tokens_used": mem_hour,
            "daily_cost_usd": mem_day,
            "source": "memory",
        }


budget_guard = BudgetGuard()


class ModelRouter:
    MODEL_POOL = {
        "default": "meta/llama-3.1-70b-instruct",
        "fast": "meta/llama-3.1-8b-instruct",
        "classify": "meta/llama-3.1-8b-instruct",
        "reasoning": "deepseek-ai/deepseek-r1-distill-llama-70b",
    }

    def select_model(self, priority: str = "normal") -> str:
        priority = (priority or "normal").lower()
        if priority in ("urgent", "vip"):
            return self.MODEL_POOL["reasoning"]
        if priority in ("fast", "low", "classify", "spam"):
            return self.MODEL_POOL["fast"]
        return self.MODEL_POOL["default"]

    def route_with_budget(
        self,
        priority: str = "normal",
        estimated_tokens: int = 0,
    ) -> Dict[str, str | bool]:
        model = self.select_model(priority)
        allowed = budget_guard.check_budget(model, estimated_tokens)
        return {
            "model": model,
            "allowed": allowed["allowed"],
            "reason": allowed["reason"],
            "budget_key": allowed.get("budget_key"),
        }


model_router = ModelRouter()
