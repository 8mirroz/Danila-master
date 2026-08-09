"""
PartsOps AI Manager v3 — Budget Guard
Контроль расходов на LLM-вызовы (токен-бюджет + cost-бюджет).

Honesty multi-worker:
- In-process ring buffer is write-through only.
- check_budget aggregates from LLMUsageLog (DB) when available, so
  separate uvicorn/worker processes share the same counters.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """Настройки бюджета для модели."""

    model_name: str
    token_budget_per_hour: int
    cost_budget_per_day_usd: float


@dataclass
class UsageRecord:
    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float = 0.0


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BudgetGuard:
    """
    Движок контроля бюджета LLM.
    - token_budget_per_hour — максимум токенов в час
    - cost_budget_per_day_usd — максимум долларов в день
    """

    DEFAULT_CONFIGS = {
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

    def _config_for(self, model: str) -> Optional[BudgetConfig]:
        if model in self._configs:
            return self._configs[model]
        # Optional global default (off by default so unknown models stay unlimited)
        if os.environ.get("PARTSOPS_LLM_APPLY_DEFAULT_BUDGET", "0") in {"1", "true", "yes"}:
            return BudgetConfig(
                model_name=model,
                token_budget_per_hour=int(os.environ.get("PARTSOPS_LLM_TOKEN_BUDGET_HOUR", "150000")),
                cost_budget_per_day_usd=float(os.environ.get("PARTSOPS_LLM_COST_BUDGET_DAY", "15.0")),
            )
        return None

    def _load_db_usage(
        self,
        model: str,
        hour_ago: datetime,
        day_ago: datetime,
    ) -> tuple[int, float]:
        """Return (hour_tokens, day_cost) from LLMUsageLog if DB available."""
        if not self._db_enabled:
            return 0, 0.0
        try:
            from sqlmodel import Session, select
            from database import engine
            from models import LLMUsageLog
        except Exception as exc:  # pragma: no cover
            logger.debug("budget DB import failed: %s", exc)
            return 0, 0.0

        hour_tokens = 0
        day_cost = 0.0
        try:
            with Session(engine) as session:
                # Hourly tokens for this model (or all if model uses default config key)
                hour_rows = session.exec(
                    select(LLMUsageLog).where(
                        LLMUsageLog.created_at >= hour_ago,
                        LLMUsageLog.model == model,
                        LLMUsageLog.status == "ok",
                    )
                ).all()
                hour_tokens = sum(int(r.total_tokens or 0) for r in hour_rows)

                day_rows = session.exec(
                    select(LLMUsageLog).where(
                        LLMUsageLog.created_at >= day_ago,
                        LLMUsageLog.model == model,
                        LLMUsageLog.status == "ok",
                    )
                ).all()
                day_cost = sum(float(r.cost_usd or 0.0) for r in day_rows)
        except Exception as exc:
            logger.debug("budget DB query failed (using memory only): %s", exc)
            return 0, 0.0
        return hour_tokens, day_cost

    def check_budget(self, model: str, tokens: int) -> Dict[str, bool | str]:
        """
        Проверить, есть ли бюджет для запроса.
        Возвращает {'allowed': bool, 'reason': str}
        """
        config = self._config_for(model)
        if config is None:
            return {"allowed": True, "reason": "no budget config (unlimited)"}

        now = _utcnow_naive()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        db_hour, db_day_cost = self._load_db_usage(model, hour_ago, day_ago)

        with self._lock:
            mem_hour = sum(
                r.total_tokens
                for r in self._usage_log
                if r.model == model and r.timestamp >= hour_ago
            )
            mem_day = sum(
                r.cost_usd
                for r in self._usage_log
                if r.model == model and r.timestamp >= day_ago
            )

        # Prefer max of DB and memory to avoid double-count when both written
        # (same process writes both). Take max so multi-worker DB is visible.
        hour_tokens = max(db_hour, mem_hour)
        day_cost = max(db_day_cost, mem_day)

        if hour_tokens + tokens > config.token_budget_per_hour:
            return {
                "allowed": False,
                "reason": (
                    f"hourly token limit exceeded: {hour_tokens}/"
                    f"{config.token_budget_per_hour}"
                ),
            }

        estimated_cost = (tokens / 1000) * 0.002
        if day_cost + estimated_cost > config.cost_budget_per_day_usd:
            return {
                "allowed": False,
                "reason": (
                    f"daily cost limit exceeded: ${day_cost:.2f}/"
                    f"${config.cost_budget_per_day_usd}"
                ),
            }

        return {
            "allowed": True,
            "reason": "within budget",
            "hourly_tokens_used": hour_tokens,
            "daily_cost_usd": day_cost,
            "source": "db+memory" if self._db_enabled else "memory",
        }

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
    ) -> None:
        """Записать использование токенов после вызова (memory ring)."""
        record = UsageRecord(
            timestamp=_utcnow_naive(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
        )
        with self._lock:
            self._usage_log.append(record)
            # Bound memory: keep ~6h of records max
            if len(self._usage_log) > 5000:
                cutoff = _utcnow_naive() - timedelta(hours=6)
                self._usage_log = [r for r in self._usage_log if r.timestamp >= cutoff]

    def get_usage_stats(self, model: Optional[str] = None) -> Dict:
        """Статистика использования (за текущий день/час)."""
        now = _utcnow_naive()
        day_ago = now - timedelta(days=1)
        hour_ago = now - timedelta(hours=1)

        with self._lock:
            records: List[UsageRecord] = list(self._usage_log)
            if model:
                records = [r for r in records if r.model == model]

        day_cost = sum(r.cost_usd for r in records if r.timestamp >= day_ago)
        hour_tokens = sum(r.total_tokens for r in records if r.timestamp >= hour_ago)

        if model:
            db_hour, db_day = self._load_db_usage(model, hour_ago, day_ago)
            hour_tokens = max(hour_tokens, db_hour)
            day_cost = max(day_cost, db_day)

        return {
            "hourly_tokens_used": hour_tokens,
            "daily_cost_usd": day_cost,
        }


# Singleton
budget_guard = BudgetGuard()


# ──────────────────────────────────────────────
# Model Router
# ──────────────────────────────────────────────


class ModelRouter:
    """
    Маршрутизатор моделей: выбирает модель по priority + budget.
    """

    MODEL_POOL = {
        "default": "meta/llama-3.1-70b-instruct",
        "fast": "meta/llama-3.1-8b-instruct",
        "classify": "meta/llama-3.1-8b-instruct",
        "reasoning": "deepseek-ai/deepseek-r1-distill-llama-70b",
    }

    def select_model(self, priority: str = "normal") -> str:
        """
        Выбрать модель по приоритету.
        - urgent/vip → reasoning
        - classify/low/fast → fast (экономия)
        - normal → default
        """
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
        """Выбрать модель с проверкой бюджета."""
        model = self.select_model(priority)
        allowed = budget_guard.check_budget(model, estimated_tokens)
        return {
            "model": model,
            "allowed": allowed["allowed"],
            "reason": allowed["reason"],
        }


# Singleton model_router
model_router = ModelRouter()
