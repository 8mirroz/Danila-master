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
    Оркестратор агентов: intake parse через единый facade (app.agents.intake_facade).
    """

    def __init__(self) -> None:
        from app.agents.intake_facade import parse_intake_text
        self._process = parse_intake_text

    def run(self, req: OrchestrationRequest) -> OrchestrationResponse:
        """
        Выполнить intake parse для инфо-запроса.
        """
        try:
            vehicle_context = None
            if req.vehicle_vin:
                vehicle_context = {"vin": req.vehicle_vin}
            result = self._process(
                req.raw_request,
                priority=req.priority,
                vehicle_context=vehicle_context,
                tenant_id=req.tenant_id,
            )

            return OrchestrationResponse(
                request_id=result.get("request_id", "unknown"),
                status=result.get("status") or result.get("validation_status") or "processed",
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