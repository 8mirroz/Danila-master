"""
PartsOps AI Manager v3 — Base Agent Interface
Контракт: 04_BACKEND_CONTRACTS/agents/base_agent.py
Определяет интерфейс агента и единый импорт.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict, Protocol


class AgentContext(TypedDict, total=False):
    """Контекст исполнения агента (общий для всех агентов)."""
    raw_request: str
    tenant_id: str
    role: str
    request_id: str
    trace: List[str]


class Agent(ABC):
    """Базовый класс агента."""

    name: str = "base_agent"

    @abstractmethod
    def run(self, context: AgentContext) -> Dict[str, Any]:
        """
        Выполнить работу агента.
        Возвращает обновлённый контекст (может быть пустой dict).
        """
        ...

    def __call__(self, context: AgentContext) -> Dict[str, Any]:
        return self.run(context)


# ──────────────────────────────────────────────
# Agent Registry (для динамической регистрации)
# ──────────────────────────────────────────────

_AGENT_REGISTRY: Dict[str, type[Agent]] = {}


def register_agent(agent_cls: type[Agent]) -> type[Agent]:
    _AGENT_REGISTRY[agent_cls.name] = agent_cls
    return agent_cls


def get_agent(name: str) -> Optional[type[Agent]]:
    return _AGENT_REGISTRY.get(name)


def list_agents() -> List[str]:
    return sorted(_AGENT_REGISTRY.keys())


# ──────────────────────────────────────────────
# Imports из реального implementation (agents.py)
# ──────────────────────────────────────────────

# Экспортируем реальные функции как "агенты" для обратной совместимости
# Интерфейс функций из agents.py уже LangGraph-совместим