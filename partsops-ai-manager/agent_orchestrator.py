"""
PartsOps AI Manager v3 — Agent Orchestrator
Контракт: 04_BACKEND_CONTRACTS/agents/agent_orchestrator.py
API-обёртка над существующей реализацией agents.py (LangGraph graph).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OrchestrationRequest(BaseModel):
    """Ввод для оркестратора."""
    raw_request: str
    customer_name: str = "Unknown"
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    vehicle_vin: Optional[str] = None
    priority: str = "normal"
    tenant_id: str = "default"
    role: str = "manager"


class OrchestrationResponse(BaseModel):
    """Выход оркестратора."""
    request_id: str
    status: str = "processed"
    result: Optional[Dict[str, Any]] = None
    trace: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class AgentOrchestrator:
    """
    Оркестратор агентов: запускает LangGraph workflow и возвращает структурированный результат.
    Инкапсулирует импорт из agents.py для единообразия API.
    """

    def __init__(self) -> None:
        # Импортируем реальную функцую из agents.py
        from agents import process_intake_request
        self._process = process_intake_request

    def run(self, req: OrchestrationRequest) -> OrchestrationResponse:
        """
        Выполнить workflow для инфо-запроса.
        """
        try:
            result = self._process(
                raw_request=req.raw_request,
                customer_name=req.customer_name,
                customer_phone=req.customer_phone,
                customer_email=req.customer_email,
                vehicle_vin=req.vehicle_vin,
                priority=req.priority,
            )

            return OrchestrationResponse(
                request_id=result.get("request_id", "unknown"),
                status=result.get("status", "processed"),
                result=result,
                trace=result.get("agent_trace", []),
            )
        except Exception as e:
            return OrchestrationResponse(
                request_id="",
                status="error",
                result=None,
                error=str(e),
            )


# Singleton
orchestrator = AgentOrchestrator()


# ──────────────────────────────────────────────
# Convenience function
# ──────────────────────────────────────────────

def process_request(
    raw_request: str,
    customer_name: str = "Unknown",
    priority: str = "normal",
) -> OrchestrationResponse:
    """Быстрый вызов оркестратора."""
    return orchestrator.run(
        OrchestrationRequest(
            raw_request=raw_request,
            customer_name=customer_name,
            priority=priority,
        )
    )