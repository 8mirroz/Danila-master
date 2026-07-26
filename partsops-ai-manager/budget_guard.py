"""
PartsOps AI Manager v3 — Budget Guard
Контракт: 04_BACKEND_CONTRACTS/budget_guard.py
Контроль расходов на LLM-вызовы (токен-бюджет + cost-бюджет).
"""

from __future__ import annotations

from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import threading


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
    }

    def __init__(self) -> None:
        self._usage_log: list[UsageRecord] = []
        self._lock = threading.Lock()
        self._configs: Dict[str, BudgetConfig] = dict(self.DEFAULT_CONFIGS)

    def register_config(self, config: BudgetConfig) -> None:
        self._configs[config.model_name] = config

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def check_budget(self, model: str, tokens: int) -> Dict[str, bool | str]:
        """
        Проверить, есть ли бюджет для запроса.
        Возвращает {'allowed': bool, 'reason': str}
        """
        config = self._configs.get(model)
        if config is None:
            return {"allowed": True, "reason": "no budget config (unlimited)"}

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        with self._lock:
            hour_tokens = sum(
                r.total_tokens for r in self._usage_log
                if r.model == model and r.timestamp >= hour_ago
            )
            day_cost = sum(
                r.cost_usd for r in self._usage_log
                if r.model == model and r.timestamp >= day_ago
            )

        if hour_tokens + tokens > config.token_budget_per_hour:
            return {
                "allowed": False,
                "reason": f"hourly token limit exceeded: {hour_tokens}/{config.token_budget_per_hour}",
            }

        # Cost estimation (на наш случай считаем $ per 1k токенов)
        estimated_cost = (tokens / 1000) * 0.002  # приблизительно
        if day_cost + estimated_cost > config.cost_budget_per_day_usd:
            return {
                "allowed": False,
                "reason": f"daily cost limit exceeded: ${day_cost:.2f}/${config.cost_budget_per_day_usd}",
            }

        return {"allowed": True, "reason": "within budget"}

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
    ) -> None:
        """Записать использование токенов после вызова."""
        record = UsageRecord(
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
        )
        with self._lock:
            self._usage_log.append(record)

    def get_usage_stats(self, model: Optional[str] = None) -> Dict:
        """Статистика использования (за текущий день/час)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        day_ago = now - timedelta(days=1)
        hour_ago = now - timedelta(hours=1)

        with self._lock:
            records = self._usage_log
            if model:
                records = [r for r in records if r.model == model]

        day_cost = sum(r.cost_usd for r in records if r.timestamp >= day_ago)
        hour_tokens = sum(r.total_tokens for r in records if r.timestamp >= hour_ago)

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
    Контракт: 04_BACKEND_CONTRACTS/model_router.py
    """

    MODEL_POOL = {
        "default": "meta/llama-3.1-70b-instruct",
        "fast": "meta/llama-3.1-8b-instruct",
        "reasoning": "deepseek-ai/deepseek-r1-distill-llama-70b",
    }

    def select_model(self, priority: str = "normal") -> str:
        """
        Выбрать модель по приоритету.
        - urgent/vip → reasoning (лучшее качество)
        - normal → default
        - low/fast → fast (экономим токены)
        """
        priority = priority.lower()
        if priority in ("urgent", "vip"):
            return self.MODEL_POOL["reasoning"]
        if priority == "fast":
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